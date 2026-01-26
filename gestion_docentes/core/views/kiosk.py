from django.shortcuts import render


def kiosco_page(request):
    return render(request, "kiosco.html")
