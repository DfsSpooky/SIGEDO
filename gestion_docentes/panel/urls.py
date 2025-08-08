from django.urls import path
from . import views

app_name = 'panel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('<str:app_label>/<str:model_name>/', views.model_list_view, name='model_list'),
    path('<str:app_label>/<str:model_name>/add/', views.ModelCreateView.as_view(), name='model_add'),
    path('<str:app_label>/<str:model_name>/<int:pk>/change/', views.ModelUpdateView.as_view(), name='model_change'),
    path('<str:app_label>/<str:model_name>/<int:pk>/delete/', views.ModelDeleteView.as_view(), name='model_delete'),
]
