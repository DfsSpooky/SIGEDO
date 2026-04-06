from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import DocumentoForm, VersionDocumentoForm
from ..models import Documento, TipoDocumento, VersionDocumento


@login_required
def subir_documento(request):
    tipos_documento = TipoDocumento.objects.all()  # Obtenemos todas las categorías

    if request.method == "POST":
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.docente = request.user
            # El estado por defecto 'RECIBIDO' se asigna desde el modelo
            documento.save()

            VersionDocumento.objects.create(
                documento=documento, archivo=form.cleaned_data["archivo"]
            )

            messages.success(
                request,
                f'El documento "{documento.titulo}" se ha subido correctamente.',
            )
            return redirect("lista_documentos")
    else:
        form = DocumentoForm()

    context = {
        "form": form,
        "tipos_documento": tipos_documento,  # Le pasamos las categorías a la plantilla
    }
    return render(request, "subir_documento.html", context)


@login_required
def subir_nueva_version(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id, docente=request.user)

    if request.method == "POST":
        form = VersionDocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            nueva_version = form.save(commit=False)
            nueva_version.documento = documento
            nueva_version.save()

            # Opcional: Cambiar el estado del documento a "En Revisión"
            documento.estado = "EN_REVISION"
            documento.save()

            messages.success(
                request, f'Se ha subido una nueva versión para "{documento.titulo}".'
            )
            return redirect("lista_documentos")
    else:
        form = VersionDocumentoForm()

    context = {"form": form, "documento": documento}
    return render(request, "subir_version.html", context)


@login_required
def lista_documentos(request):
    documentos_qs = (
        Documento.objects.filter(docente=request.user)
        .prefetch_related("versiones")
        .order_by("-fecha_subida")
    )

    # Definir el orden de los estados
    status_order = ["OBSERVADO", "EN_REVISION", "RECIBIDO", "APROBADO", "VENCIDO"]

    # Agrupar documentos por estado
    documentos_agrupados = {status: [] for status in status_order}
    for doc in documentos_qs:
        if doc.estado in documentos_agrupados:
            documentos_agrupados[doc.estado].append(doc)

    # Crear una lista ordenada de tuplas (nombre_visible_estado, lista_documentos)
    # para pasarla a la plantilla, omitiendo grupos vacíos.
    documentos_por_seccion = []
    estado_display_map = dict(Documento.ESTADOS_DOCUMENTO)

    for status_key in status_order:
        if documentos_agrupados[status_key]:
            documentos_por_seccion.append(
                {
                    "estado_key": status_key,
                    "estado_display": estado_display_map.get(status_key, status_key),
                    "documentos": documentos_agrupados[status_key],
                }
            )

    return render(
        request,
        "lista_documentos.html",
        {"documentos_por_seccion": documentos_por_seccion},
    )
