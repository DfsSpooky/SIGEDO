from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('panel/', include('panel.urls', namespace='panel')),
    path('', include('core.urls')),
    path('accounts/', include('django.contrib.auth.urls')), # Para login, logout, etc.
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)