# -*- coding: utf-8 -*-
from django.http import HttpResponse
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from ..models import Docente, Asistencia, Curso, ConfiguracionInstitucion
from io import BytesIO
# Se quita urlopen porque ya no es necesario
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
        
        logo_img = Paragraph("AQUI VA EL LOGO", STYLES['Normal'])
        
        # --- CAMBIO: Se lee la imagen desde la ruta del archivo, no desde una URL ---
        if self.configuracion and self.configuracion.logo and hasattr(self.configuracion.logo, 'path'):
            try:
                # Se usa la ruta directa del archivo, que es más confiable
                logo_path = self.configuracion.logo.path
                logo_img = Image(logo_path, width=1.2*inch, height=1.2*inch, hAlign='CENTER')
            except Exception as e:
                print(f"Error cargando logo para PDF desde la ruta: {e}")
        # --- FIN DEL CAMBIO ---

        nombre_institucion = Paragraph(self.configuracion.nombre_institucion if self.configuracion else "Nombre de Institución", STYLES['InstitutionTitle'])
        if self.configuracion and self.configuracion.facultad:
            nombre_facultad = Paragraph(self.configuracion.facultad.nombre.upper(), STYLES['FacultyTitle'])
        else:
            nombre_facultad = Spacer(0, 0)
        titulo_reporte = Paragraph("REPORTE DE ASISTENCIA DOCENTE", STYLES['ReportTitle'])
        periodo_reporte = Paragraph(f"Periodo del {self.fecha_inicio} al {self.fecha_fin}", STYLES['ReportSubtitle'])
        header_text_content = [nombre_institucion, nombre_facultad, titulo_reporte, periodo_reporte]
        
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
                    if tiene_tardanza:
                        estado_dia = 'Tardanza'
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
        'No Requerido': STYLES['TableCellCenter'],
    }

    # Llenar la tabla con los datos procesados
    for record in reporte_final:
        docente_cell = Paragraph(f"{record['docente'].last_name}, {record['docente'].first_name}", STYLES['TableCell'])
        fecha_cell = Paragraph(record['fecha'].strftime('%d/%m/%Y'), STYLES['TableCellCenter'])
        estado_cell = Paragraph(record['estado'], status_styles.get(record['estado'], STYLES['TableCellCenter']))
        
        detalles_cells = []
        if record['asistencias']:
            for asis in record['asistencias']:
                hora_entrada_str = asis.hora_entrada.astimezone(peru_tz).strftime('%H:%M:%S') if asis.hora_entrada else "--:--"
                detalle_str = f"• {asis.curso.nombre} (Entrada: {hora_entrada_str})"
                if asis.es_tardanza:
                    detalle_str += " <font color='orange'><b>(TARDE)</b></font>"
                detalles_cells.append(Paragraph(detalle_str, STYLES['TableCellSmall']))
        else:
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

# --- Función de exportación a Excel (sin cambios) ---
def exportar_reporte_excel(request):
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    curso_id = request.GET.get('curso')
    asistencias_qs = Asistencia.objects.filter(fecha__range=[fecha_inicio, fecha_fin]).select_related('docente', 'curso')
    docentes = Docente.objects.all().order_by('last_name', 'first_name')
    if curso_id:
        docentes_con_asistencia_en_curso_ids = asistencias_qs.filter(curso_id=curso_id).values_list('docente_id', flat=True).distinct()
        docentes = docentes.filter(id__in=docentes_con_asistencia_en_curso_ids)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Reporte_Asistencia_{fecha_inicio}_a_{fecha_fin}.xlsx"'
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Reporte de Asistencia"
    headers = ["Docente", "DNI", "Asistencia General", "Detalle de Cursos"]
    worksheet.append(headers)
    for docente in docentes:
        asistencias_docente = asistencias_qs.filter(docente=docente)
        asistencia_general = asistencias_docente.filter(curso__isnull=True).first()
        asistencias_cursos = asistencias_docente.filter(curso__isnull=False)
        asistencia_general_str = "Ausente"
        if asistencia_general:
            asistencia_general_str = f"Presente ({asistencia_general.hora_entrada.strftime('%H:%M')})"
        cursos_list = []
        for asistencia_curso in asistencias_cursos:
            if asistencia_curso.hora_entrada:
                entrada = asistencia_curso.hora_entrada.strftime('%H:%M')
                salida = asistencia_curso.hora_salida.strftime('%H:%M') if asistencia_curso.hora_salida else '--:--'
                cursos_list.append(f"{asistencia_curso.curso.nombre} (Entrada: {entrada}, Salida: {salida})")
        cursos_str = "N/A"
        if cursos_list:
            cursos_str = " | ".join(cursos_list)
        worksheet.append([f"{docente.last_name}, {docente.first_name}", docente.dni, asistencia_general_str, cursos_str])
    workbook.save(response)
    return response