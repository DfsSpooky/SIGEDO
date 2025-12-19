from collections import defaultdict
from datetime import date, timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.templatetags.static import static
from django.utils import timezone

from core.models import Asistencia, Docente
from core.utils.reports import _generar_datos_reporte_asistencia
from core.utils.responses import (
    not_found_response,
    server_error_response,
    success_response,
)


@staff_member_required
def api_get_report_chart_data(request):
    report_data, _ = _generar_datos_reporte_asistencia(request.GET)

    daily_stats = defaultdict(
        lambda: {"Presente": 0, "Falta": 0, "Tardanza": 0, "Justificado": 0}
    )

    for record in report_data:
        if record["estado"] in ["Presente", "Falta", "Tardanza", "Justificado"]:
            fecha_str = record["fecha"].strftime("%d/%m")
            daily_stats[fecha_str][record["estado"]] += 1

    sorted_labels = sorted(
        daily_stats.keys(), key=lambda d: timezone.datetime.strptime(d, "%d/%m").date()
    )

    bar_chart_data = {
        "labels": sorted_labels,
        "presentes": [daily_stats[label]["Presente"] for label in sorted_labels],
        "faltas": [daily_stats[label]["Falta"] for label in sorted_labels],
        "tardanzas": [daily_stats[label]["Tardanza"] for label in sorted_labels],
    }

    total_presentes = sum(bar_chart_data["presentes"])
    total_faltas = sum(bar_chart_data["faltas"])
    total_tardanzas = sum(bar_chart_data["tardanzas"])

    pie_chart_data = {
        "presentes": total_presentes,
        "faltas": total_faltas,
        "tardanzas": total_tardanzas,
    }

    return success_response(
        data={"bar_chart": bar_chart_data, "pie_chart": pie_chart_data}
    )


@staff_member_required
def detalle_asistencia_docente_ajax(request, docente_id):
    try:
        docente = Docente.objects.get(pk=docente_id)

        fecha_inicio_str = request.GET.get("fecha_inicio")
        fecha_fin_str = request.GET.get("fecha_fin")

        try:
            fecha_inicio = (
                timezone.datetime.strptime(fecha_inicio_str, "%Y-%m-%d").date()
                if fecha_inicio_str
                else date.today() - timedelta(days=30)
            )
            fecha_fin = (
                timezone.datetime.strptime(fecha_fin_str, "%Y-%m-%d").date()
                if fecha_fin_str
                else date.today()
            )
        except (ValueError, TypeError):
            fecha_fin = date.today()
            fecha_inicio = fecha_fin - timedelta(days=30)

        asistencias_cursos = (
            Asistencia.objects.filter(
                docente=docente,
                curso__isnull=False,
                fecha__range=[fecha_inicio, fecha_fin],
            )
            .select_related("curso")
            .order_by("-fecha", "-hora_entrada")
        )

        data = {
            "docente": {
                "nombre_completo": f"{docente.first_name} {docente.last_name}",
                "dni": docente.dni,
                "foto_url": (
                    docente.foto.url
                    if docente.foto and hasattr(docente.foto, "url")
                    else static("placeholder.png")
                ),
            },
            "asistencias_cursos": [
                {
                    "curso": asis.curso.nombre if asis.curso else "N/A",
                    "fecha": asis.fecha.strftime("%d/%m/%Y"),
                    "hora_entrada": (
                        asis.hora_entrada.strftime("%I:%M %p")
                        if asis.hora_entrada
                        else "-"
                    ),
                    "hora_salida": (
                        asis.hora_salida.strftime("%I:%M %p")
                        if asis.hora_salida
                        else "-"
                    ),
                    "foto_entrada_url": (
                        asis.foto_entrada.url if asis.foto_entrada else None
                    ),
                    "foto_salida_url": (
                        asis.foto_salida.url if asis.foto_salida else None
                    ),
                }
                for asis in asistencias_cursos
            ],
        }
        return success_response(data=data)
    except Docente.DoesNotExist:
        return not_found_response("Docente no encontrado")
    except Exception as e:
        return server_error_response(f"Error inesperado: {str(e)}")
