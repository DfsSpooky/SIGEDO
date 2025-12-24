from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Importamos las URLs de la API para pasarlas explícitamente al schema view
import core.api.urls

schema_view = get_schema_view(
   openapi.Info(
      title="Gestion Docentes API",
      default_version='v1',
      description="Documentación de la API para el Sistema de Gestión Docente",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contacto@institucion.edu"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
   patterns=[path('api/', include('core.api.urls'))], # Force scan of API URLs
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("accounts/", include("django.contrib.auth.urls")),  # Para login, logout, etc.

    # Swagger / ReDoc
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
