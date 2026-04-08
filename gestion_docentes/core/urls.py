from django.urls import path, include
from . import views, urls_inventario, urls_reservas
from django.contrib.auth import views as auth_views
from .utils import exports

urlpatterns = [
    path('subir_documento/', views.subir_documento, name='subir_documento'),
    path('documentos/<int:documento_id>/subir_version/', views.subir_nueva_version, name='subir_nueva_version'),
    path('documentos/', views.lista_documentos, name='lista_documentos'),
    path('asistencia/', views.registrar_asistencia, name='asistencia'),
    path('', views.dashboard, name='dashboard'),
    path('perfil/', views.perfil, name='perfil'),
    path('horarios/<int:carrera_id>/', views.ver_horarios, name='ver_horarios'),
    path('horarios/<int:carrera_id>/generar/', views.generar_horarios, name='generar_horarios'),
    path('intercambio/<int:curso_id>/', views.solicitar_intercambio, name='solicitar_intercambio'),
    path('solicitudes/', views.ver_solicitudes, name='ver_solicitudes'),
    path('solicitudes/<int:solicitud_id>/responder/', views.responder_solicitud, name='responder_solicitud'),
    
    # --- Justificaciones ---
    path('justificaciones/', views.lista_justificaciones, name='lista_justificaciones'),
    path('justificaciones/solicitar/', views.solicitar_justificacion, name='solicitar_justificacion'),

    # --- Inventario ---
    path('inventario/', include(urls_inventario)),

    # --- Reservas de Equipos ---
    path('reservas/', include(urls_reservas)),

    # --- Custom Login/Logout Views ---
    path('accounts/login/', views.custom_login_view, name='login'),
    # Django's built-in logout view is fine, as settings.py handles the redirect
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),

    # --- URLS PARA EL KIOSCO ---
    # Esta ruta mostrará la página del kiosco
    path('kiosco/', views.kiosco_page, name='kiosco_page'),

    # --- URLs de la API (ahora en su propio módulo) ---
    # Se agrupan todas las URLs de la API bajo el prefijo /api/
    path('api/', include('core.api.urls', namespace='api')),
    
    # Las URLs de la API que antes estaban aquí han sido movidas a core/api/urls.py

    # --- INICIO DE URLS PARA CREDENCIALES ---
    path('credenciales/', views.lista_docentes_credenciales, name='lista_credenciales'),
    path('credenciales/<str:encrypted_id>/', views.generar_credencial_docente, name='generar_credencial'),
    path('credenciales/<int:docente_id>/rotate-qr/', views.rotate_qr_code, name='rotate_qr_code'),
    # --- FIN DE URLS PARA CREDENCIALES ---
    path('reportes/asistencia/', views.reporte_asistencia, name='reporte_asistencia'),

    path('planificador/', views.planificador_horarios, name='planificador_horarios'),

    path('horarios/ver/', views.vista_publica_horarios, name='vista_publica_horarios'),

    path('reporte-asistencia/', views.reporte_asistencia, name='reporte_asistencia'),
    path('reportes/analiticas/', views.analytics_dashboard, name='analytics_dashboard'),
    # Las URLs de exportación ahora apuntan al nuevo módulo
    path('reporte-asistencia/excel/', exports.exportar_reporte_excel, name='exportar_excel'),
    path('reporte-asistencia/pdf/', exports.exportar_reporte_pdf, name='exportar_pdf'),
    path('notificaciones/', views.ver_notificaciones, name='ver_notificaciones'),
    path('anuncios/', views.ver_anuncios, name='ver_anuncios'),
    path('docente/<int:docente_id>/ficha/', views.generar_ficha_docente, name='generar_ficha_docente'),
]