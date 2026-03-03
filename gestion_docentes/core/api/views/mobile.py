import base64
from datetime import timedelta

from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.serializers import DocenteInfoSerializer, CursoAsistenciaSerializer, MobileUpdateProfileSerializer, RecuperacionClaseSerializer, MobileMarkAttendanceSerializer
from core.models import Curso, Asistencia, AsistenciaDiaria, Semestre, RecuperacionClase, AdelantoClase, Documento, VersionDocumento, TipoDocumento, Anuncio
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from core.api.views.utils import get_kiosk_data_for_docente


class MobileStatusView(APIView):
    """
    API View para obtener la información del docente autenticado y sus cursos del día.
    Utilizada por la App Móvil.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        docente = request.user
        response_data = get_kiosk_data_for_docente(docente, request)
        return Response(response_data)


class MobilePublicConfigView(APIView):
    """
    API View pública para obtener la configuración de la institución (Logo, Nombre).
    No requiere autenticación.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        from core.models.settings import ConfiguracionInstitucion
        from core.api.serializers import ConfiguracionInstitucionSerializer
        
        config = ConfiguracionInstitucion.load()
        serializer = ConfiguracionInstitucionSerializer(config, context={'request': request})
        return Response(serializer.data)


class MobileMarkAttendanceView(APIView):
    """
    API View para marcar asistencia desde la App Móvil.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = MobileMarkAttendanceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "message": "Datos inválidos.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated_data = serializer.validated_data
        action_type = validated_data["actionType"]
        photo_base64 = validated_data.get("photoBase64")
        observation = validated_data.get("observation")
        latitude = validated_data.get("latitude")
        longitude = validated_data.get("longitude")
        
        # Handle Multipart file if present
        photo_file_multipart = request.FILES.get('photo') 

        # --- VALIDACIÓN GEOLOCALIZACIÓN ---
        from core.models.settings import ConfiguracionInstitucion
        config = ConfiguracionInstitucion.load()
        
        es_valido, resultado = config.validar_ubicacion(latitude, longitude)
        if not es_valido:
            return Response(
                {"status": "error", "message": resultado},
                status=status.HTTP_400_BAD_REQUEST
            )
        # ----------------------------------

        docente = request.user
        today = timezone.localtime(timezone.now()).date()
        now = timezone.now()

        photo_file = None
        
        # 1. Prioridad: Multipart File
        if 'photo' in request.FILES:
            photo_file = request.FILES['photo']
        
        # 2. Fallback: Base64 (Legacy/Web)
        elif photo_base64:
            try:
                format, imgstr = photo_base64.split(";base64,")
                ext = format.split("/")[-1]
                photo_file = ContentFile(
                    base64.b64decode(imgstr),
                    name=f"{docente.username}_{now.timestamp()}.{ext}",
                )
            except:
                return Response(
                    {"status": "error", "message": "Formato de photoBase64 inválido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
        # Validación de FOTO OBLIGATORIA para ENTRADAS
        if action_type in ["general_entry", "course_entry"] and not photo_file:
             return Response(
                {"status": "error", "message": "La foto es obligatoria para marcar entrada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action_type == "general_entry":
            # Validar Horario Configurado
            local_time = timezone.localtime(now).time()
            if config.hora_inicio_asistencia_general and local_time < config.hora_inicio_asistencia_general:
                return Response(
                    {"status": "error", "message": f"El registro de entrada inicia a las {config.hora_inicio_asistencia_general.strftime('%H:%M')}."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if config.hora_fin_asistencia_general and local_time > config.hora_fin_asistencia_general:
                 return Response(
                    {"status": "error", "message": f"El registro de entrada finalizó a las {config.hora_fin_asistencia_general.strftime('%H:%M')}."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            _, created = AsistenciaDiaria.objects.get_or_create(
                docente=docente, fecha=today, defaults={"foto_verificacion": photo_file}
            )
            if created:
                return Response(
                    {
                        "status": "success",
                        "message": "Entrada general registrada correctamente.",
                    }
                )
            else:
                return Response(
                    {
                        "status": "success",
                        "message": "La entrada general ya ha sido marcada hoy.",
                        "data": {"already_marked": True},
                    }
                )

        elif action_type == "general_exit":
            asistencia_diaria = AsistenciaDiaria.objects.filter(
                docente=docente, fecha=today
            ).first()

            if not asistencia_diaria:
                return Response(
                    {
                        "status": "error",
                        "message": "Debe marcar la entrada general antes de marcar la salida.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if asistencia_diaria.hora_salida:
                return Response(
                    {
                        "status": "warning",
                        "message": "La salida general ya ha sido marcada hoy.",
                    }
                )

            asistencia_diaria.hora_salida = now
            if photo_file:
                asistencia_diaria.foto_salida = photo_file
            asistencia_diaria.save()

            return Response(
                {
                    "status": "success",
                    "message": "Salida general registrada correctamente.",
                }
            )

        elif action_type in ["course_entry", "course_exit"]:
            curso_id = validated_data.get("courseId")
            if not curso_id:
                return Response(
                    {
                        "status": "error",
                        "message": "courseId es requerido para esta acción.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                curso = Curso.objects.get(id=curso_id)
            except Curso.DoesNotExist:
                return Response(
                    {"status": "error", "message": "Curso no encontrado."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            asistencia, _ = Asistencia.objects.get_or_create(
                docente=docente, curso=curso, fecha=today
            )
            response_data = {}

            if action_type == "course_entry":
                from core.services.attendance_service import can_mark_entry, calculate_allowed_exit_time
                
                can_mark, error_msg, bloque_del_dia = can_mark_entry(docente, curso, now)
                if not can_mark:
                    code = "TOO_EARLY" if "inicio" in error_msg else "ERROR"
                    return Response(
                        {"status": "error", "message": error_msg, "code": code},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                asistencia.hora_entrada = now
                asistencia.foto_entrada = photo_file
                asistencia.hora_salida_permitida = calculate_allowed_exit_time(bloque_del_dia, now)
                
                response_data["es_tardanza"] = asistencia.es_tardanza()
                asistencia.save()

            elif action_type == "course_exit":
                if not asistencia.hora_entrada:
                    return Response(
                        {
                            "status": "error",
                            "message": "Debe marcar la entrada antes de poder marcar la salida.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if asistencia.hora_salida:
                    return Response(
                        {
                            "status": "warning",
                            "message": "La salida para este curso ya fue marcada.",
                        }
                    )
                
                if not asistencia.puede_marcar_salida:
                    return Response(
                        {
                            "status": "error",
                            "message": "Aún no puede marcar la salida. No se ha cumplido el tiempo mínimo.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                asistencia.hora_salida = now
                if photo_file:
                    asistencia.foto_salida = photo_file
                if observation:
                    asistencia.observacion_salida = observation
                asistencia.save()

            return Response(
                {
                    "status": "success",
                    "message": "Asistencia registrada correctamente.",
                    "data": response_data,
                }
            )

        return Response(
            {"status": "error", "message": "Tipo de acción no válida."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class MobileUpdateProfileView(APIView):
    """
    API View para actualizar el perfil del docente (celular y foto).
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def patch(self, request, *args, **kwargs):
        from core.api.serializers import MobileUpdateProfileSerializer
        
        docente = request.user
        serializer = MobileUpdateProfileSerializer(docente, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                "status": "success", 
                "message": "Perfil actualizado correctamente",
                "data": {
                    "celular": docente.celular,
                    "foto": request.build_absolute_uri(docente.foto.url) if docente.foto else None
                }
            })
        
        return Response(
            {"status": "error", "message": "Datos inválidos", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )


class UpdateFCMTokenView(APIView):
    """
    API View para actualizar el token FCM del usuario.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        token = request.data.get('fcm_token')
        if not token:
            return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        user.fcm_token = token
        user.save()
        return Response({'status': 'success', 'message': 'Token updated successfully'})

class MobileDocumentsView(APIView):
    """
    API View para obtener la lista de documentos del docente (Misma lógica que web).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # 1. Obtener documentos existentes
        docs_existentes = (
            Documento.objects.filter(docente=request.user)
            .select_related("tipo_documento")
            .prefetch_related("versiones")
            .order_by("-fecha_subida")
        )

        # 2. Identificar tipos faltantes
        ids_tipos_subidos = docs_existentes.values_list('tipo_documento_id', flat=True)
        tipos_faltantes = TipoDocumento.objects.exclude(id__in=ids_tipos_subidos)

        # 3. Definir orden status
        status_order = ["PENDIENTE", "OBSERVADO", "EN_REVISION", "RECIBIDO", "APROBADO", "VENCIDO"]
        
        # 4. Agrupar logicamente
        documentos_agrupados = {status: [] for status in status_order}

        # Distribución de Existentes
        for doc in docs_existentes:
            if doc.estado in documentos_agrupados:
                ultima_version = doc.versiones.first()
                documentos_agrupados[doc.estado].append({
                    "isDummy": False,
                    "id": doc.id,
                    "titulo": doc.titulo,
                    "tipo": doc.tipo_documento.nombre,
                    "tipoId": doc.tipo_documento.id,
                    "fechaSubida": doc.fecha_subida.strftime("%d %b, %Y") if doc.fecha_subida else "--",
                    "fechaVencimiento": doc.fecha_vencimiento.strftime("%d %b, %Y") if doc.fecha_vencimiento else None,
                    "estado": doc.estado,
                    "archivoUrl": ultima_version.archivo.url if ultima_version and ultima_version.archivo else None,
                    "version": ultima_version.numero_version if ultima_version else None,
                })

        # Distribución de Pendientes (Dummies)
        for tipo in tipos_faltantes:
            documentos_agrupados["PENDIENTE"].append({
                "isDummy": True,
                "id": 0,
                "titulo": f"{tipo.nombre}", # Title as Type Name for clarity in mobile card
                "tipo": tipo.nombre,
                "tipoId": tipo.id,
                "fechaSubida": None,
                "fechaVencimiento": None,
                "estado": "PENDIENTE",
                "archivoUrl": None,
                "version": None,
            })

        # 5. Construir respuesta con secciones
        estado_display_map = dict(Documento.ESTADOS_DOCUMENTO)
        estado_display_map["PENDIENTE"] = "Pendientes de Entrega"

        sections_list = []
        for status_key in status_order:
            docs = documentos_agrupados[status_key]
            if docs:
                sections_list.append({
                    "sectionTitle": estado_display_map.get(status_key, status_key),
                    "statusKey": status_key,
                    "documents": docs
                })
        
        return Response(sections_list)


class MobileUploadDocumentView(APIView):
    """
    API View para subir documentos desde el móvil.
    Maneja tanto la creación inicial como nuevas versiones si ya existe el documento.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        tipo_id = request.data.get('tipo_id')
        archivo = request.FILES.get('archivo')

        if not tipo_id or not archivo:
            return Response(
                {"error": "Faltan datos requeridos (tipo_id, archivo)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            tipo_doc = TipoDocumento.objects.get(id=tipo_id)
        except TipoDocumento.DoesNotExist:
            return Response(
                {"error": "Tipo de documento inválido"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Buscar si ya existe documento para este tipo y usuario
        documento = Documento.objects.filter(
            docente=request.user, 
            tipo_documento=tipo_doc
        ).first()

        if documento:
            # Caso: Subir nueva versión
            VersionDocumento.objects.create(
                documento=documento,
                archivo=archivo
            )
            # Actualizar estado a EN_REVISION si estaba observado o vencido
            # O simplemente 'RECIBIDO'/'EN_REVISION' para indicar cambio.
            # Según views/documents.py -> subir_nueva_version pone 'EN_REVISION'
            documento.estado = "EN_REVISION"
            documento.save()
            action = "updated"
        else:
            # Caso: Nuevo documento
            documento = Documento.objects.create(
                docente=request.user,
                tipo_documento=tipo_doc,
                titulo=f"{tipo_doc.nombre} - {request.user.get_full_name()}", # Título autogenerado
                estado="RECIBIDO"
            )
            VersionDocumento.objects.create(
                documento=documento,
                archivo=archivo
            )
            action = "created"


        return Response({
            "status": "success",
            "action": action,
            "document_id": documento.id,
            "message": "Documento subido correctamente"
        })


class MobileAdelantoClaseView(APIView):
    """
    API View para registrar un adelanto de clase.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        course_id = request.data.get('courseId')
        reason = request.data.get('reason')

        if not course_id or not reason:
             return Response(
                {"status": "error", "message": "Faltan datos (courseId, reason)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            curso = Curso.objects.get(id=course_id)
        except Curso.DoesNotExist:
            return Response(
                {"status": "error", "message": "Curso no encontrado."},
                 status=status.HTTP_404_NOT_FOUND
            )

        # Crear el adelanto (usando update_or_create para evitar duplicados el mismo día)
        AdelantoClase.objects.update_or_create(
            docente=request.user,
            curso=curso,
            fecha=timezone.localtime(timezone.now()).date(),
            defaults={'motivo': reason}
        )

        return Response({
            "status": "success",
            "message": "Adelanto de clase registrado correctamente. Ahora puede marcar su entrada."
        })


class MobileDirectorAttendanceView(APIView):
    """
    API View para que el Director (o Staff) monitoree la asistencia en tiempo real.
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get(self, request, *args, **kwargs):
        # 1. Validar Permisos (Director/Staff)
        if not request.user.is_staff:
             return Response(
                {"status": "error", "message": "No tiene permisos para ver esta información."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        today = timezone.localdate()
        
        # 2. Obtener Asistencias de Curso (Hoy)
        # Filtramos las que tengan marca de entrada
        asistencias_curso = (
            Asistencia.objects.filter(fecha=today, hora_entrada__isnull=False)
            .select_related('docente', 'curso')
            .prefetch_related('curso__especialidades')
        )

        # 3. Obtener Asistencias Generales (Hoy)
        asistencias_general = (
            AsistenciaDiaria.objects.filter(fecha=today)
            .select_related('docente')
        )
        
        events = []
        
        # Helper para formatear
        def format_time(dt):
            if not dt: return None
            return timezone.localtime(dt).strftime("%I:%M %p")

        # Procesar Cursos
        for a in asistencias_curso:
            specialties = ", ".join([e.nombre for e in a.curso.especialidades.all()])
            # Timestamp para ordenamiento
            ts = a.hora_salida or a.hora_entrada
            
            events.append({
                "type": "COURSE",
                "id": a.id,
                "teacherName": a.docente.get_full_name(),
                "teacherPhoto": request.build_absolute_uri(a.docente.foto.url) if a.docente.foto else None,
                "courseName": a.curso.nombre,
                "specialty": specialties,
                "entryTime": format_time(a.hora_entrada),
                "exitTime": format_time(a.hora_salida),
                "isLate": a.es_tardanza(),
                "timestamp": ts
            })
            
        # Procesar Generales
        for g in asistencias_general:
            ts = g.hora_salida or g.hora_entrada
            events.append({
                "type": "GATE",
                "id": g.id,
                "teacherName": g.docente.get_full_name(),
                "teacherPhoto": request.build_absolute_uri(g.docente.foto.url) if g.docente.foto else None,
                "courseName": "Control General",
                "specialty": "Ingreso/Salida Campus",
                "entryTime": format_time(g.hora_entrada),
                "exitTime": format_time(g.hora_salida),
                "isLate": False,
                "timestamp": ts
            })
            
        # Ordenar por el más reciente (descendente)
        # Manejar caso de timestamp None (aunque con el filtro no deberia pasar mucho)
        events.sort(key=lambda x: x['timestamp'] or timezone.now(), reverse=True)
        
        # Limpiar timestamp
        for e in events:
            del e['timestamp']

        return Response(events)


class MobileDirectorStatsView(APIView):
    """
    API View para estadísticas del Director (Gráficos).
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get(self, request, *args, **kwargs):
        if not request.user.is_staff:
             return Response(status=status.HTTP_403_FORBIDDEN)

        today = timezone.localdate()
        # 1. Weekly Attendance (Last 7 days or current week)
        # Let's do current week (Mon-Sun)
        start_week = today - timedelta(days=today.weekday())
        weekly_stats = []
        days_map = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        
        for i in range(7):
            day = start_week + timedelta(days=i)
            # Count distinct teachers who attended (Course or Gate)
            # This is a bit complex, let's simplify: Count total attendance events
            count_course = Asistencia.objects.filter(fecha=day, hora_entrada__isnull=False).count()
            count_gate = AsistenciaDiaria.objects.filter(fecha=day).count()
            weekly_stats.append({
                "day": days_map[i],
                "count": count_course + count_gate
            })

        # 2. Lateness Percentage (Today, Course Only)
        course_attendance_today = Asistencia.objects.filter(fecha=today, hora_entrada__isnull=False)
        total_course = course_attendance_today.count()
        late_count = 0
        for a in course_attendance_today:
            if a.es_tardanza():
                late_count += 1
        
        lateness_pct = (late_count / total_course * 100) if total_course > 0 else 0

        # 3. Attendance by Career (Today, Course Only)
        # We need to aggregate by Curso__carrera__nombre
        from django.db.models import Count
        career_stats = (
            course_attendance_today
            .values('curso__carrera__nombre')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        career_data = [
            {"name": item['curso__carrera__nombre'], "count": item['count']} 
            for item in career_stats
        ]

        return Response({
            "weekly_attendance": weekly_stats,
            "lateness_percentage": round(lateness_pct, 1),
            "attendance_by_career": career_data
        })


class MobileAttendanceHistoryView(APIView):
    """
    API View para obtener el historial de asistencia del docente (Mensual).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        docente = request.user
        
        # Obtener mes y año de los params o usar actual
        now = timezone.now()
        try:
            month = int(request.query_params.get('month', now.month))
            year = int(request.query_params.get('year', now.year))
        except ValueError:
            month = now.month
            year = now.year

        # Definir rango de fechas
        import calendar
        from datetime import date
        _, last_day = calendar.monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)

        # 1. Obtener Asistencias Generales (Campus)
        asistencias_general = AsistenciaDiaria.objects.filter(
            docente=docente,
            fecha__range=[start_date, end_date]
        ).order_by('fecha')

        # 2. Obtener Asistencias a Clases
        asistencias_cursos = Asistencia.objects.filter(
            docente=docente,
            fecha__range=[start_date, end_date]
        ).select_related('curso').order_by('fecha')

        # 3. Agrupar por día
        history_by_day = {}

        # Helper
        def get_day_entry(date_obj):
            if date_obj not in history_by_day:
                history_by_day[date_obj] = {
                    "date": date_obj.strftime("%Y-%m-%d"),
                    "dayName": date_obj.strftime("%A"), 
                    "general": None,
                    "courses": []
                }
            return history_by_day[date_obj]

        def format_time(dt):
            if not dt: return None
            return timezone.localtime(dt).strftime("%I:%M %p")

        # Procesar General
        for g in asistencias_general:
            entry = get_day_entry(g.fecha)
            entry["general"] = {
                "entryTime": format_time(g.hora_entrada),
                "exitTime": format_time(g.hora_salida),
                "status": "COMPLETED" if g.hora_entrada and g.hora_salida else ("INCOMPLETE" if g.hora_entrada else "ABSENT")
            }

        # Procesar Cursos
        for c in asistencias_cursos:
            entry = get_day_entry(c.fecha)
            entry["courses"].append({
                "courseName": c.curso.nombre,
                "entryTime": format_time(c.hora_entrada),
                "exitTime": format_time(c.hora_salida),
                "isLate": c.es_tardanza(),
                "status": "COMPLETED" if c.hora_entrada and c.hora_salida else ("IN_PROGRESS" if c.hora_entrada else "--")
            })

        # Convertir a lista y ordenar
        response_list = sorted(history_by_day.values(), key=lambda x: x['date'], reverse=True)
        return Response(response_list)


class MobileRecuperacionClaseView(APIView):
    """
    API View para gestionar solicitudes de recuperación de clases.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        solicitudes = RecuperacionClase.objects.filter(docente=request.user).order_by('-fecha_creacion')
        serializer = RecuperacionClaseSerializer(solicitudes, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = RecuperacionClaseSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(docente=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
