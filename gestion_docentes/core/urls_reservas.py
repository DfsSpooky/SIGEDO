from django.urls import path
from . import views

app_name = 'reservas'

urlpatterns = [
    path('', views.DisponibilidadEquiposView.as_view(), name='disponibilidad'),
    path('mis-reservas/', views.MisReservasView.as_view(), name='mis_reservas'),
    path('<int:pk>/cancelar/', views.cancelar_reserva, name='cancelar'),
]
