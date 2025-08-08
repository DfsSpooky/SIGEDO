from django.urls import path
from . import views

app_name = 'panel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('<str:app_label>/<str:model_name>/', views.model_list_view, name='model_list'),
]
