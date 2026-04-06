from datetime import date

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import permission_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..models import Curso, Docente, Especialidad, Semestre
from ..utils.exports import exportar_ficha_docente_pdf
from ..utils.reports import _generar_datos_reporte_asistencia


@staff_member_required
@permission_required("core.view_reporte", raise_exception=True)
def reporte_asistencia(request):
    reporte_final, total_docentes = _generar_datos_reporte_asistencia(request.GET)

    presentes_count = len([r for r in reporte_final if r["estado"] == "Presente"])
    ausentes_count = len([r for r in reporte_final if r["estado"] == "Falta"])

    paginator = Paginator(reporte_final, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    if "page" in query_params:
        del query_params["page"]

    context = {
        "page_obj": page_obj,
        "reporte_data": page_obj.object_list,
        "total_docentes": total_docentes,
        "presentes_count": presentes_count,
        "ausentes_count": ausentes_count,
        "docentes": Docente.objects.all().order_by("last_name"),  # Para el nuevo filtro
        "cursos": Curso.objects.all(),
        "especialidades": Especialidad.objects.all(),
        "fecha_inicio": request.GET.get(
            "fecha_inicio", date.today().strftime("%Y-%m-%d")
        ),
        "fecha_fin": request.GET.get("fecha_fin", date.today().strftime("%Y-%m-%d")),
        "estado": request.GET.get("estado", "todos"),
        "curso_id": request.GET.get("curso"),
        "especialidad_id": request.GET.get("especialidad"),
        "docente_id": request.GET.get("docente"),  # Para el nuevo filtro
        "filter_params": query_params.urlencode(),
    }
    return render(request, "reporte_asistencia.html", context)


@staff_member_required
@permission_required("core.view_reporte", raise_exception=True)
def analytics_dashboard(request):
    """
    Displays the analytics dashboard with charts and stats for administrators.
    """
    # The data is fetched asynchronously by the frontend.
    # This view can pass filter options like date ranges or semester lists if needed.
    context = {
        "semestres": Semestre.objects.all().order_by("-fecha_inicio"),
        "especialidades": Especialidad.objects.all(),
    }
    return render(request, "analytics_dashboard.html", context)


@staff_member_required
def generar_ficha_docente(request, docente_id):
    docente = get_object_or_404(Docente, id=docente_id)
    semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()
    if not semestre_activo:
        messages.error(request, "No hay un semestre activo para generar la ficha.")
        return redirect("perfil")

    pdf = exportar_ficha_docente_pdf(docente, semestre_activo)

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="ficha_integral_{docente.username}.pdf"'
    )
    return response
