from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Case, When, Value, IntegerField

from ..forms import DocumentoForm, VersionDocumentoForm
from ..models import Documento, TipoDocumento, VersionDocumento

@login_required
def subir_documento(request):
    # Si recibimos un 'tipo_id' por URL, intentamos pre-seleccionar ese tipo
    initial_data = {}
    tipo_preseleccionado = request.GET.get('tipo_id')
    if tipo_preseleccionado:
        initial_data = {'tipo_documento': tipo_preseleccionado}

    if request.method == "POST":
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.docente = request.user
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
        form = DocumentoForm(initial=initial_data)

    context = {
        "form": form,
        # Pasamos los tipos para que la plantilla pueda usarlos si es necesario
        "tipos_documento": TipoDocumento.objects.all(), 
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
    # 1. Obtener documentos existentes del docente
    docs_existentes = (
        Documento.objects.filter(docente=request.user)
        .select_related("tipo_documento")
        .prefetch_related("versiones")
        .order_by("-fecha_subida")
    )

    # 2. Identificar qué Tipos de Documento existen en el sistema pero NO han sido subidos
    ids_tipos_subidos = docs_existentes.values_list('tipo_documento_id', flat=True)
    tipos_faltantes = TipoDocumento.objects.exclude(id__in=ids_tipos_subidos)

    # 3. Definir orden de visualización (Pendientes primero es mejor UX)
    status_order = ["PENDIENTE", "OBSERVADO", "EN_REVISION", "RECIBIDO", "APROBADO", "VENCIDO"]
    
    documentos_agrupados = {status: [] for status in status_order}

    # 4. Agregar los documentos "Reales" a su grupo correspondiente
    for doc in docs_existentes:
        if doc.estado in documentos_agrupados:
            documentos_agrupados[doc.estado].append(doc)

    # 5. Crear documentos "Ficticios" para los pendientes
    # Esto permite que la plantilla los trate igual, pero con estado 'PENDIENTE'
    for tipo in tipos_faltantes:
        documentos_agrupados["PENDIENTE"].append({
            "is_dummy": True, # Bandera para el frontend
            "id": 0,
            "titulo": f"{tipo.nombre} (No entregado)",
            "tipo_documento": tipo, # Objeto tipo para acceder a .nombre e .id
            "fecha_subida": None,
            "fecha_vencimiento": None,
            "estado": "PENDIENTE",
            "versiones": []
        })

    # 6. Preparar estructura final para la plantilla
    documentos_por_seccion = []
    estado_display_map = dict(Documento.ESTADOS_DOCUMENTO)
    estado_display_map["PENDIENTE"] = "Pendientes de Entrega" # Etiqueta personalizada

    for status_key in status_order:
        if documentos_agrupados[status_key]:
            documentos_por_seccion.append({
                "estado_key": status_key,
                "estado_display": estado_display_map.get(status_key, status_key),
                "documentos": documentos_agrupados[status_key]
            })

    return render(
        request,
        "lista_documentos.html",
        {"documentos_por_seccion": documentos_por_seccion},
    )