from django.urls import path
from . import views

app_name = 'inventario'

urlpatterns = [
    path('', views.ActivoListView.as_view(), name='lista'),
    path('nuevo/', views.ActivoCreateView.as_view(), name='crear'),
    path('<int:pk>/', views.ActivoDetailView.as_view(), name='detalle'),
    path('<int:pk>/editar/', views.ActivoUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.ActivoDeleteView.as_view(), name='eliminar'),
]
