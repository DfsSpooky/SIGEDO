import uuid

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse

from ..models import ConfiguracionInstitucion, Docente, PersonalDocente
from ..utils.encryption import decrypt_id


@staff_member_required
def lista_docentes_credenciales(request):
    query = request.GET.get("q", "")
    docentes = PersonalDocente.objects.all()

    if query:
        docentes = docentes.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(dni__icontains=query)
        ).distinct()

    context = {
        "docentes": docentes,
        "query": query,
    }
    return render(request, "lista_credenciales.html", context)


@staff_member_required
def generar_credencial_docente(request, encrypted_id):
    docente_id = decrypt_id(encrypted_id)
    if docente_id is None:
        raise Http404("El enlace de la credencial no es válido o ha expirado.")

    docente = get_object_or_404(PersonalDocente, id=docente_id)
    configuracion = ConfiguracionInstitucion.load()

    # Preparamos la URL absoluta para la FOTO del docente
    foto_url_absoluta = ""
    if docente.foto and hasattr(docente.foto, "url"):
        foto_url_absoluta = request.build_absolute_uri(docente.foto.url)
    else:
        foto_url_absoluta = request.build_absolute_uri(static("placeholder.png"))

    # --- CORRECCIÓN PARA EL LOGO ---
    # Ahora también preparamos la URL absoluta para el LOGO de la institución
    logo_url_absoluto = ""
    if configuracion and configuracion.logo and hasattr(configuracion.logo, "url"):
        logo_url_absoluto = request.build_absolute_uri(configuracion.logo.url)
    # --- FIN DE LA CORRECCIÓN ---

    # Preparamos el contexto completo para la plantilla
    context = {
        "docente": docente,
        "configuracion": configuracion,
        "foto_url_absoluta": foto_url_absoluta,
        "logo_url_absoluto": logo_url_absoluto,  # Pasamos la nueva variable del logo
    }

    return render(request, "credencial.html", context)


@staff_member_required
def rotate_qr_code(request, docente_id):
    """
    Generates a new id_qr for a given docente, effectively invalidating the old one.
    """
    docente = get_object_or_404(Docente, id=docente_id)
    docente.id_qr = uuid.uuid4()
    docente.save()
    messages.success(
        request,
        f"Se ha generado un nuevo código QR para {docente.get_full_name()}. La credencial anterior ya no es válida.",
    )
    # Redirect back to the admin change page for that user
    return redirect(reverse("admin:core_personaldocente_change", args=[docente.id]))
