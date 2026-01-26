from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render

from ..models import ConfiguracionInstitucion


def custom_login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    configuracion = ConfiguracionInstitucion.load()

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect("dashboard")
        # Si el form no es válido, se renderiza de nuevo la página con los errores
    else:
        form = AuthenticationForm()

    return render(
        request,
        "registration/login.html",
        {"form": form, "configuracion": configuracion},
    )
