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


# --- Función exportar_reporte_pdf (sin cambios) ---
def exportar_reporte_pdf(request):
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    curso_id = request.GET.get('curso')

    asistencias_qs = Asistencia.objects.filter(fecha__range=[fecha_inicio, fecha_fin]).select_related('docente', 'curso')
    
    docentes = Docente.objects.all().order_by('last_name', 'first_name').prefetch_related('especialidades')
    
    curso_filtrado = None
    if curso_id:
        try:
            curso_filtrado = Curso.objects.get(id=curso_id)
            docentes_con_asistencia_en_curso_ids = asistencias_qs.filter(curso_id=curso_id).values_list('docente_id', flat=True).distinct()
            docentes = docentes.filter(id__in=docentes_con_asistencia_en_curso_ids)
        except Curso.DoesNotExist:
            curso_id = None

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Reporte_Asistencia_{fecha_inicio}_a_{fecha_fin}.pdf"'
    buffer = BytesIO()
    
    template_kwargs = {
        'pagesize': landscape(letter), 'leftMargin': 0.5*inch, 'rightMargin': 0.5*inch,
        'topMargin': 0.5*inch, 'bottomMargin': 0.5*inch, 'request': request,
        'configuracion': ConfiguracionInstitucion.load(), 'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin
    }
    
    elements = [Spacer(1, 1.0*inch)]
    
    criterios_header = Paragraph("<b>Criterios del Reporte</b>", STYLES['Normal'])
    if curso_filtrado:
        criterios_detail = Paragraph(f"Filtrado por curso: <b>{curso_filtrado.nombre}</b>", STYLES['Normal'])
    else:
        criterios_detail = Paragraph("Mostrando <b>todos</b> los docentes", STYLES['Normal'])
    criterios_data = [[criterios_header], [criterios_detail]]
    criterios_table = Table(criterios_data, colWidths=['100%'])
    criterios_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BACKGROUND', (0,0), (-1,-1), colors.Color(0.95, 0.95, 0.95)),
        ('BOX', (0,0), (-1,-1), 1, colors.lightgrey), ('LEFTPADDING', (0,0), (-1,-1), 10), 
        ('RIGHTPADDING', (0,0), (-1,-1), 10), ('TOPPADDING', (0,0), (-1,-1), 6), 
        ('BOTTOMPADDING', (0,0), (-1,-1), 6), ('LINEBELOW', (0,0), (0,0), 1, colors.lightgrey)
    ]))
    elements.append(criterios_table)
    elements.append(Spacer(1, 0.2*inch))
    
    table_headers = ["Docente", "Especialidad", "Asistencia General", "Detalle de Asistencias por Curso"]
    table_data = [[Paragraph(txt, STYLES['TableHeader']) for txt in table_headers]]
    
    for docente in docentes:
        asistencias_docente = asistencias_qs.filter(docente=docente)
        asistencia_general = asistencias_docente.filter(curso__isnull=True).first()
        asistencias_cursos = list(asistencias_docente.filter(curso__isnull=False).select_related('curso'))

        especialidades_list = [esp.nombre for esp in docente.especialidades.all()]
        especialidades_str = ", ".join(especialidades_list) if especialidades_list else "No asignada"
        especialidades_cell = Paragraph(especialidades_str, STYLES['TableCell'])

        if asistencia_general:
            asistencia_general_cell = Paragraph("Presente", STYLES['StatusPresente'])
        else:
            asistencia_general_cell = Paragraph("Ausente", STYLES['StatusAusente'])
        
        cursos_cells = []
        if asistencias_cursos:
            for asistencia_curso in asistencias_cursos:
                if asistencia_curso.hora_entrada:
                    entrada = f"Entrada: {asistencia_curso.hora_entrada.strftime('%H:%M')}"
                    salida = f"Salida: {asistencia_curso.hora_salida.strftime('%H:%M')}" if asistencia_curso.hora_salida else "Salida: --:--"
                    cursos_cells.append(Paragraph(f"• {asistencia_curso.curso.nombre} <i>({entrada} | {salida})</i>", STYLES['TableCellSmall']))
        else:
            cursos_cells.append(Paragraph("Sin clases asignadas en el periodo.", STYLES['TableCellSmall']))

        table_data.append([
            Paragraph(f"{docente.last_name}, {docente.first_name}", STYLES['TableCell']),
            especialidades_cell,
            asistencia_general_cell,
            cursos_cells
        ])

    table = Table(table_data, colWidths=[2.2*inch, 2.5*inch, 1.5*inch, 3.3*inch], repeatRows=1)
    
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