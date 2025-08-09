# -*- coding: utf-8 -*-
from django.http import HttpResponse
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from ..models import Docente, Asistencia, Curso, ConfiguracionInstitucion, Justificacion, AsistenciaDiaria, Documento
from io import BytesIO
from django.utils import timezone

# ... (El resto de los estilos no cambia) ...
STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle(name='InstitutionTitle', fontName='Helvetica-Bold', fontSize=16, alignment=1, spaceAfter=4))
STYLES.add(ParagraphStyle(name='FacultyTitle', fontName='Helvetica-Bold', fontSize=12, alignment=1, spaceAfter=12, textColor=colors.darkslategray))
STYLES.add(ParagraphStyle(name='ReportTitle', fontName='Helvetica-Bold', fontSize=11, alignment=1, spaceAfter=2))
STYLES.add(ParagraphStyle(name='ReportSubtitle', fontName='Helvetica', fontSize=9, alignment=1, spaceAfter=8))
STYLES.add(ParagraphStyle(name='TableHeader', fontName='Helvetica-Bold', fontSize=10, textColor=colors.whitesmoke))
STYLES.add(ParagraphStyle(name='TableCell', fontName='Helvetica', fontSize=9, textColor=colors.darkslategray, leading=12))
STYLES.add(ParagraphStyle(name='TableCellCenter', parent=STYLES['TableCell'], alignment=1))
STYLES.add(ParagraphStyle(name='TableCellSmall', fontName='Helvetica', fontSize=8, textColor=colors.darkslategray))
STYLES.add(ParagraphStyle(name='StatusPresente', parent=STYLES['TableCellCenter'], backColor=colors.mediumseagreen, textColor=colors.white, borderRadius=4, borderPadding=(6, 2)))
STYLES.add(ParagraphStyle(name='StatusAusente', parent=STYLES['TableCellCenter'], backColor=colors.lightcoral, textColor=colors.white, borderRadius=4, borderPadding=(6, 2)))
STYLES.add(ParagraphStyle(name='StatusJustificado', parent=STYLES['TableCellCenter'], backColor=colors.lightblue, textColor=colors.black, borderRadius=4, borderPadding=(6, 2)))


class ReportePDFTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        self.request = kwargs.pop('request', None)
        self.configuracion = kwargs.pop('configuracion', None)
        self.fecha_inicio = kwargs.pop('fecha_inicio', '')
        self.fecha_fin = kwargs.pop('fecha_fin', '')
        super().__init__(filename, **kwargs)
        self.page_count = 0
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id='normal')
        template = PageTemplate(id='main_template', frames=[frame], onPage=self._draw_header_footer)
        self.addPageTemplates([template])

    def _draw_header_footer(self, canvas, doc):
        canvas.saveState()
        
        logo_img = Paragraph("LOGO", STYLES['Normal'])
        
        if self.configuracion and self.configuracion.logo and hasattr(self.configuracion.logo, 'path'):
            try:
                logo_img = Image(self.configuracion.logo.path, width=1.2*inch, height=1.2*inch, hAlign='CENTER')
            except Exception as e:
                print(f"Error loading logo for PDF: {e}")

        # DEBUGGING
        debug_info = f"DEBUG: PDF - {self.configuracion.nombre_institucion} / {self.configuracion.nombre_dashboard}"
        debug_paragraph = Paragraph(debug_info, STYLES['TableCellSmall'])
        # END DEBUGGING

        nombre_institucion = Paragraph(self.configuracion.nombre_institucion if self.configuracion else "Nombre de Institución", STYLES['InstitutionTitle'])
        if self.configuracion and self.configuracion.facultad:
            nombre_facultad = Paragraph(self.configuracion.facultad.nombre.upper(), STYLES['FacultyTitle'])
        else:
            nombre_facultad = Spacer(0, 0)
        titulo_reporte = Paragraph("REPORTE DE ASISTENCIA DOCENTE", STYLES['ReportTitle'])
        periodo_reporte = Paragraph(f"Periodo del {self.fecha_inicio} al {self.fecha_fin}", STYLES['ReportSubtitle'])
        header_text_content = [debug_paragraph, nombre_institucion, nombre_facultad, titulo_reporte, periodo_reporte]
        
        header_table = Table([[logo_img, header_text_content]], colWidths=[1.5*inch, 8.0*inch])
        header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
        
        w, h = header_table.wrapOn(canvas, self.width, self.topMargin)
        header_table.drawOn(canvas, self.leftMargin, self.height + self.topMargin - h + 0.3*inch)
        
        canvas.setStrokeColorRGB(0.8, 0.8, 0.8)
        canvas.line(self.leftMargin, self.height + self.topMargin - h + 0.2*inch, self.width + self.leftMargin, self.height + self.topMargin - h + 0.2*inch)
        
        fecha_generacion = Paragraph(f"Generado el: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S')}", STYLES['TableCellSmall'])
        numero_pagina = Paragraph(f"Página {doc.page} de {self.page_count}", STYLES['TableCellSmall'])
        footer_table = Table([[fecha_generacion, numero_pagina]], colWidths=[self.width/2, self.width/2])
        footer_table.setStyle(TableStyle([('ALIGN', (0,0), (0,0), 'LEFT'), ('ALIGN', (1,0), (1,0), 'RIGHT')]))
        w, h = footer_table.wrapOn(canvas, self.width, self.bottomMargin)
        footer_table.drawOn(canvas, self.leftMargin, h)
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if hasattr(flowable, 'style') and flowable.style.name == 'TableHeader':
            self.page_count = self.page

# El resto del archivo (la función exportar_reporte_pdf) no necesita cambios
# ... (todo el código desde la línea 'def exportar_reporte_pdf(request):' hasta el final se mantiene igual)
# PEGAR AQUÍ EL RESTO DEL ARCHIVO exports.py QUE YA TIENES


from ..models import Semestre
from datetime import date, timedelta, time
import pytz

def exportar_reporte_pdf(request):
    # 1. OBTENER Y PROCESAR FILTROS (Lógica idéntica a la vista)
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    estado_filtro = request.GET.get('estado', 'todos')
    curso_id = request.GET.get('curso')
    especialidad_id = request.GET.get('especialidad')

    try:
        fecha_inicio = timezone.datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date() if fecha_inicio_str else date.today()
        fecha_fin = timezone.datetime.strptime(fecha_fin_str, '%Y-%m-%d').date() if fecha_fin_str else date.today()
    except ValueError:
        fecha_inicio = fecha_fin = date.today()

    # 2. OBTENER Y FILTRAR DATOS (Lógica idéntica a la vista)
    docentes_qs = Docente.objects.all().order_by('last_name', 'first_name')
    if especialidad_id:
        docentes_qs = docentes_qs.filter(especialidades__id=especialidad_id)

    asistencias_qs = Asistencia.objects.filter(fecha__range=[fecha_inicio, fecha_fin]).select_related('docente', 'curso')
    asistencias_diarias_qs = AsistenciaDiaria.objects.filter(fecha__range=[fecha_inicio, fecha_fin]).select_related('docente')
    asistencias_diarias_map = {(ad.docente_id, ad.fecha): ad for ad in asistencias_diarias_qs}

    semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
    cursos_programados_qs = Curso.objects.filter(semestre=semestre_activo, dia__isnull=False)
    if curso_id:
        curso_obj = cursos_programados_qs.filter(id=curso_id).first()
        if curso_obj:
            docentes_qs = docentes_qs.filter(id=curso_obj.docente_id)

    # 3. PROCESAR REPORTE (Lógica idéntica a la vista)
    reporte_final = []
    configuracion = ConfiguracionInstitucion.load()
    limite_tardanza = configuracion.tiempo_limite_tardanza or 10

    justificaciones_aprobadas = Justificacion.objects.filter(
        estado='APROBADO',
        fecha_inicio__lte=fecha_fin,
        fecha_fin__gte=fecha_inicio
    )
    justificaciones_set = set()
    for just in justificaciones_aprobadas:
        d = just.fecha_inicio
        while d <= just.fecha_fin:
            justificaciones_set.add((just.docente_id, d))
            d += timedelta(days=1)

    dias_del_rango = [fecha_inicio + timedelta(days=i) for i in range((fecha_fin - fecha_inicio).days + 1)]
    dias_semana_map = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}

    for docente in docentes_qs:
        for dia_actual in dias_del_rango:
            dia_semana_str = dias_semana_map[dia_actual.weekday()]
            cursos_del_dia = cursos_programados_qs.filter(docente=docente, dia=dia_semana_str)
            asistencias_del_dia = asistencias_qs.filter(docente=docente, fecha=dia_actual)
            estado_dia, tiene_tardanza = 'No Requerido', False
            if cursos_del_dia.exists():
                estado_dia = 'Falta'
                if asistencias_del_dia.exists():
                    estado_dia = 'Presente'
                    for asis in asistencias_del_dia:
                        if asis.hora_entrada and asis.curso.horario_inicio:
                            hora_inicio_dt = timezone.make_aware(timezone.datetime.combine(dia_actual, asis.curso.horario_inicio))
                            if (asis.hora_entrada - hora_inicio_dt) > timedelta(minutes=limite_tardanza):
                                asis.es_tardanza = True
                                tiene_tardanza = True
                            else:
                                asis.es_tardanza = False
                    if tiene_tardanza:
                        estado_dia = 'Tardanza'

            if estado_dia == 'Falta':
                if (docente.id, dia_actual) in justificaciones_set:
                    estado_dia = 'Justificado'

            if estado_filtro == 'todos' or estado_dia.lower() == estado_filtro:
                if estado_dia != 'No Requerido' or estado_filtro == 'todos':
                    reporte_final.append({'docente': docente, 'fecha': dia_actual, 'estado': estado_dia, 'asistencias': asistencias_del_dia})

    # 4. GENERACIÓN DEL PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Reporte_Asistencia_{fecha_inicio_str}_a_{fecha_fin_str}.pdf"'
    buffer = BytesIO()
    
    template_kwargs = {
        'pagesize': landscape(letter), 'leftMargin': 0.5*inch, 'rightMargin': 0.5*inch,
        'topMargin': 0.5*inch, 'bottomMargin': 0.5*inch, 'request': request,
        'configuracion': configuracion, 'fecha_inicio': fecha_inicio_str, 'fecha_fin': fecha_fin_str
    }
    doc = ReportePDFTemplate(buffer, **template_kwargs)
    elements = [Spacer(1, 1.0*inch)]
    
    # Definir la zona horaria de Perú
    peru_tz = pytz.timezone('America/Lima')

    # Encabezados de la tabla
    table_headers = ["Fecha", "Docente", "Estado", "Detalle de Asistencias"]
    table_data = [[Paragraph(txt, STYLES['TableHeader']) for txt in table_headers]]
    
    # Estilos para los estados
    status_styles = {
        'Presente': STYLES['StatusPresente'],
        'Tardanza': ParagraphStyle(name='StatusTardanza', parent=STYLES['TableCellCenter'], backColor=colors.orange, textColor=colors.white, borderRadius=4, borderPadding=(6, 2)),
        'Falta': STYLES['StatusAusente'],
        'Justificado': STYLES['StatusJustificado'],
        'No Requerido': STYLES['TableCellCenter'],
    }

    # Llenar la tabla con los datos procesados
    for record in reporte_final:
        docente_cell = Paragraph(f"{record['docente'].last_name}, {record['docente'].first_name}", STYLES['TableCell'])
        fecha_cell = Paragraph(record['fecha'].strftime('%d/%m/%Y'), STYLES['TableCellCenter'])
        estado_cell = Paragraph(record['estado'], status_styles.get(record['estado'], STYLES['TableCellCenter']))
        
        detalles_cells = []
        asistencia_diaria = asistencias_diarias_map.get((record['docente'].id, record['fecha']))

        if asistencia_diaria:
            hora_general_str = asistencia_diaria.hora_entrada.astimezone(peru_tz).strftime('%H:%M:%S')
            detalle_general_str = f"<b>Asistencia General: {hora_general_str}</b>"
            detalles_cells.append(Paragraph(detalle_general_str, STYLES['TableCellSmall']))

            if asistencia_diaria.foto_verificacion and asistencia_diaria.foto_verificacion.storage.exists(asistencia_diaria.foto_verificacion.name):
                try:
                    foto_file = asistencia_diaria.foto_verificacion.open('rb')
                    foto_img = Image(foto_file, width=0.8*inch, height=0.8*inch, hAlign='LEFT')
                    detalles_cells.append(foto_img)
                    foto_file.close()
                except Exception:
                    detalles_cells.append(Paragraph("<i>(Error al cargar foto)</i>", STYLES['TableCellSmall']))
            detalles_cells.append(Spacer(1, 6))


        if record['asistencias']:
            for asis in record['asistencias']:
                hora_entrada_str = asis.hora_entrada.astimezone(peru_tz).strftime('%H:%M:%S') if asis.hora_entrada else "--:--"
                detalle_str = f"• {asis.curso.nombre} (Entrada: {hora_entrada_str})"
                if asis.es_tardanza:
                    detalle_str += " <font color='orange'><b>(TARDE)</b></font>"
                detalles_cells.append(Paragraph(detalle_str, STYLES['TableCellSmall']))
        elif not asistencia_diaria: # Si no hay ni asistencia diaria ni a cursos
            detalles_cells.append(Paragraph("N/A", STYLES['TableCellSmall']))

        table_data.append([fecha_cell, docente_cell, estado_cell, detalles_cells])

    table = Table(table_data, colWidths=[1.5*inch, 3*inch, 1.5*inch, 3.5*inch], repeatRows=1)
    
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.2, 0.2, 0.2)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)])
    ]))
    elements.append(table)
    
    doc = ReportePDFTemplate(buffer, **template_kwargs)
    doc.build(elements)

    response.write(buffer.getvalue())
    buffer.close()
    return response

def exportar_reporte_excel(request):
    # 1. OBTENER Y PROCESAR FILTROS (Lógica idéntica a la vista)
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    estado_filtro = request.GET.get('estado', 'todos')
    curso_id = request.GET.get('curso')
    especialidad_id = request.GET.get('especialidad')

    try:
        fecha_inicio = timezone.datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date() if fecha_inicio_str else date.today()
        fecha_fin = timezone.datetime.strptime(fecha_fin_str, '%Y-%m-%d').date() if fecha_fin_str else date.today()
    except ValueError:
        fecha_inicio = fecha_fin = date.today()

    # 2. OBTENER Y FILTRAR DATOS (Lógica idéntica a la vista)
    docentes_qs = Docente.objects.all().order_by('last_name', 'first_name')
    if especialidad_id:
        docentes_qs = docentes_qs.filter(especialidades__id=especialidad_id)

    asistencias_qs = Asistencia.objects.filter(fecha__range=[fecha_inicio, fecha_fin]).select_related('docente', 'curso')
    semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
    cursos_programados_qs = Curso.objects.filter(semestre=semestre_activo, dia__isnull=False)
    if curso_id:
        curso_obj = cursos_programados_qs.filter(id=curso_id).first()
        if curso_obj:
            docentes_qs = docentes_qs.filter(id=curso_obj.docente_id)

    # 3. PROCESAR REPORTE (Lógica idéntica a la vista, incluyendo justificaciones)
    reporte_final = []
    configuracion = ConfiguracionInstitucion.load()
    limite_tardanza = configuracion.tiempo_limite_tardanza or 10

    justificaciones_aprobadas = Justificacion.objects.filter(estado='APROBADO', fecha_inicio__lte=fecha_fin, fecha_fin__gte=fecha_inicio)
    justificaciones_set = set()
    for just in justificaciones_aprobadas:
        d = just.fecha_inicio
        while d <= just.fecha_fin:
            justificaciones_set.add((just.docente_id, d))
            d += timedelta(days=1)

    dias_del_rango = [fecha_inicio + timedelta(days=i) for i in range((fecha_fin - fecha_inicio).days + 1)]
    dias_semana_map = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}

    for docente in docentes_qs:
        for dia_actual in dias_del_rango:
            dia_semana_str = dias_semana_map[dia_actual.weekday()]
            cursos_del_dia = cursos_programados_qs.filter(docente=docente, dia=dia_semana_str)
            asistencias_del_dia = asistencias_qs.filter(docente=docente, fecha=dia_actual)
            estado_dia, tiene_tardanza = 'No Requerido', False
            if cursos_del_dia.exists():
                estado_dia = 'Falta'
                if asistencias_del_dia.exists():
                    estado_dia = 'Presente'
                    for asis in asistencias_del_dia:
                        if asis.hora_entrada and asis.curso.horario_inicio:
                            hora_inicio_dt = timezone.make_aware(timezone.datetime.combine(dia_actual, asis.curso.horario_inicio))
                            if (asis.hora_entrada - hora_inicio_dt) > timedelta(minutes=limite_tardanza):
                                tiene_tardanza = True
                    if tiene_tardanza:
                        estado_dia = 'Tardanza'
                if estado_dia == 'Falta' and (docente.id, dia_actual) in justificaciones_set:
                    estado_dia = 'Justificado'

            if estado_filtro == 'todos' or estado_dia.lower() == estado_filtro:
                if estado_dia != 'No Requerido' or estado_filtro == 'todos':
                    reporte_final.append({'docente': docente, 'fecha': dia_actual, 'estado': estado_dia, 'asistencias': asistencias_del_dia})

    # 4. GENERACIÓN DEL EXCEL
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Reporte_Asistencia_{fecha_inicio_str}_a_{fecha_fin_str}.xlsx"'
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Reporte de Asistencia"

    headers = ["Fecha", "Docente", "DNI", "Estado", "Detalle de Asistencias"]
    worksheet.append(headers)

    peru_tz = pytz.timezone('America/Lima')

    for record in reporte_final:
        docente_nombre = f"{record['docente'].last_name}, {record['docente'].first_name}"
        docente_dni = record['docente'].dni
        fecha_str = record['fecha'].strftime('%d/%m/%Y')
        estado_str = record['estado']

        detalles_list = []
        if record['asistencias']:
            for asis in record['asistencias']:
                hora_entrada_str = asis.hora_entrada.astimezone(peru_tz).strftime('%H:%M') if asis.hora_entrada else "--:--"
                detalle = f"{asis.curso.nombre} (Entrada: {hora_entrada_str})"
                # Re-calculamos la tardanza aquí para el detalle
                if asis.hora_entrada and asis.curso.horario_inicio:
                    hora_inicio_dt = timezone.make_aware(timezone.datetime.combine(record['fecha'], asis.curso.horario_inicio))
                    if (asis.hora_entrada - hora_inicio_dt) > timedelta(minutes=limite_tardanza):
                        detalle += " (TARDE)"
                detalles_list.append(detalle)

        detalles_str = " | ".join(detalles_list) if detalles_list else "N/A"

        worksheet.append([fecha_str, docente_nombre, docente_dni, estado_str, detalles_str])

    workbook.save(response)
    return response

def exportar_ficha_docente_pdf(docente, semestre_activo):
    buffer = BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=letter, leftMargin=0.75*inch, rightMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)

    # Estilos
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='FichaTitle', fontName='Helvetica-Bold', fontSize=18, spaceAfter=12, alignment=1))
    styles.add(ParagraphStyle(name='FichaSubtitle', fontName='Helvetica-Bold', fontSize=14, spaceAfter=8, textColor=colors.darkslategray))
    styles.add(ParagraphStyle(name='FichaBody', fontName='Helvetica', fontSize=10, leading=14))
    styles.add(ParagraphStyle(name='FichaBodyBold', parent=styles['FichaBody'], fontName='Helvetica-Bold'))

    elements = []

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
    template = PageTemplate(id='ficha_template', frames=[frame])
    doc.addPageTemplates([template])

    # --- Cabecera ---
    configuracion = ConfiguracionInstitucion.load()
    logo_img = Spacer(0,0)
    if configuracion.logo and configuracion.logo.storage.exists(configuracion.logo.name):
        logo_file = configuracion.logo.open('rb')
        logo_img = Image(logo_file, width=0.8*inch, height=0.8*inch)
        logo_file.close()

    header_data = [
        [logo_img, Paragraph(f"<b>{configuracion.nombre_institucion}</b><br/>{configuracion.facultad.nombre if configuracion.facultad else ''}", styles['FichaBody'])]
    ]
    header_table = Table(header_data, colWidths=[1*inch, 6*inch])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.25*inch))
    elements.append(Paragraph("Ficha Integral del Docente", styles['FichaTitle']))

    # --- Datos Personales ---
    elements.append(Paragraph("1. Datos Personales", styles['FichaSubtitle']))
    personal_data = [
        [Paragraph("<b>Nombre Completo:</b>", styles['FichaBody']), Paragraph(docente.get_full_name(), styles['FichaBody'])],
        [Paragraph("<b>DNI:</b>", styles['FichaBody']), Paragraph(docente.dni, styles['FichaBody'])],
        [Paragraph("<b>Email:</b>", styles['FichaBody']), Paragraph(docente.email, styles['FichaBody'])],
    ]
    personal_table = Table(personal_data, colWidths=[1.5*inch, 5.5*inch])
    elements.append(personal_table)
    elements.append(Spacer(1, 0.25*inch))

    # --- Carga Académica ---
    elements.append(Paragraph(f"2. Carga Académica ({semestre_activo.nombre})", styles['FichaSubtitle']))
    cursos = Curso.objects.filter(docente=docente, semestre=semestre_activo)
    if cursos.exists():
        cursos_data = [[Paragraph(f"<b>{c.nombre}</b> ({c.especialidad.nombre if c.especialidad else 'N/A'})", styles['FichaBody'])] for c in cursos]
        cursos_table = Table(cursos_data, colWidths=[7*inch])
        cursos_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.grey)]))
        elements.append(cursos_table)
    else:
        elements.append(Paragraph("No tiene cursos asignados en este semestre.", styles['FichaBody']))
    elements.append(Spacer(1, 0.25*inch))

    # --- Desempeño de Asistencia ---
    elements.append(Paragraph("3. Desempeño de Asistencia", styles['FichaSubtitle']))
    # (Lógica de cálculo de asistencia simplificada para la ficha)
    total_clases_programadas = Asistencia.objects.filter(docente=docente, curso__in=cursos).count()
    asistencias_contadas = Asistencia.objects.filter(docente=docente, curso__in=cursos, hora_entrada__isnull=False).count()
    porcentaje_asistencia = (asistencias_contadas / total_clases_programadas * 100) if total_clases_programadas > 0 else 100

    desempeno_data = [
        [Paragraph("<b>Clases Programadas en el Semestre:</b>", styles['FichaBody']), Paragraph(str(total_clases_programadas), styles['FichaBody'])],
        [Paragraph("<b>Asistencias Registradas:</b>", styles['FichaBody']), Paragraph(str(asistencias_contadas), styles['FichaBody'])],
        [Paragraph("<b>Porcentaje de Asistencia:</b>", styles['FichaBody']), Paragraph(f"{porcentaje_asistencia:.2f}%", styles['FichaBodyBold'])],
    ]
    desempeno_table = Table(desempeno_data, colWidths=[3*inch, 4*inch])
    elements.append(desempeno_table)
    elements.append(Spacer(1, 0.25*inch))

    # --- Gestión Documental ---
    elements.append(Paragraph("4. Gestión Documental", styles['FichaSubtitle']))
    documentos = Documento.objects.filter(docente=docente)
    doc_data = [[Paragraph(f"<b>{d.get_estado_display()}</b>", styles['FichaBody']), Paragraph(d.titulo, styles['FichaBody'])] for d in documentos]
    if doc_data:
        doc_table = Table(doc_data, colWidths=[1.5*inch, 5.5*inch])
        elements.append(doc_table)
    else:
        elements.append(Paragraph("No hay documentos registrados.", styles['FichaBody']))

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf