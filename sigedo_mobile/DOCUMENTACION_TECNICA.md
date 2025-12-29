# 🚀 SIGEDO Mobile - Guía de Implementación y Despliegue

Este documento resume las nuevas funcionalidades implementadas en la aplicación móvil SIGEDO y proporciona una guía crítica para el despliegue y solución de problemas, especialmente enfocada en Firebase y Android.

## ✨ Funcionalidades Implementadas

### 1. 👆 Login Biométrico (Seguridad)
- **Descripción**: Permite iniciar sesión usando Huella Digital o Desbloqueo Facial.
- **Flujo**: 
    1. Login manual exitoso -> Pregunta "¿Habilitar Biometría?".
    2. Credenciales guardadas cifradas en `SecureStorage`.
    3. Siguientes inicios: Botón "Ingresar con Huella".
- **Componentes**: `BiometricService`, `SecureStorage`, `MainActivity` (FlutterFragmentActivity).

### 2. 📝 Justificaciones con Adjuntos
- **Descripción**: Formulario para solicitar justificaciones de inasistencia.
- **Mejora**: Soporte para adjuntar **Fotos** (Cámara/Galería) y documentos **PDF**.
- **Técnico**: Conversión a Base64 antes de enviar a la API Django.

### 3. 🔔 Notificaciones Push (Firebase FCM)
- **Descripción**: Recepción de alertas en tiempo real (ej: "Justificación Aprobada").
- **Infraestructura**: Integración con Firebase Cloud Messaging (FCM).
- **Manejo**: Notificaciones en segundo plano (System Tray) y primer plano (Local Notification).

### 4. 📍 Geolocalización Anti-Fraude
- **Descripción**: Validación de distancia (radio 100m) al marcar asistencia.
- **Configuración**: Permisos de ubicación en Android Manifest.

### 5. 🎨 Modernización UI/UX
- **Diseño**: "Premium" con paleta de colores moderna, Google Fonts, y tarjetas con sombras suaves.
- **Navegación**: Menú inferior (BottomNavigationBar) persistente.

---

## 🔧 Guía de Despliegue y Configuración (Tips Críticos)

### 1. 🔥 Firebase (Lo más delicado)
Para que las notificaciones y el login funcionen en producción (Release) o en otros dispositivos PC:

*   **Archivo `google-services.json`**:
    *   **NO** subir a repositorios públicos (GitHub).
    *   Debe estar presente en `android/app/google-services.json` siempre.
*   **Huellas SHA-1**:
    *   Firebase requiere la huella digital (SHA-1) de la clave con la que firmas la app.
    *   **Debug**: Si cambias de PC, la huella `debug.keystore` cambia. Debes agregar la nueva SHA-1 en la consola de Firebase.
    *   **Release**: Cuando generes el APK final (`flutter build apk --release`), asegúrate de registrar la SHA-1 de tu `upload-keystore.jks` en Firebase.

### 2. 🤖 Android Build & Errores Comunes

#### Error: "Requires core library desugaring"
*   **Causa**: Usar librerías modernas (como las de notificaciones) que usan Java 8.
*   **Solución**: En `android/app/build.gradle.kts`:
    ```kotlin
    compileOptions {
        isCoreLibraryDesugaringEnabled = true
        // ...
    }
    dependencies {
        coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.0.3")
    }
    ```

#### Error: "Ambiguous reference... bigLargeIcon"
*   **Causa**: Conflicto entre versiones de `androidx.core` y `flutter_local_notifications`.
*   **Solución**: Usar `flutter_local_notifications: ^17.0.0` o superior en `pubspec.yaml`, que corrige internamente la ambigüedad.

#### Error: "Building with plugins requires symlink support" (Windows)
*   **Causa**: Windows restringe la creación de enlaces simbólicos por defecto.
*   **Solución**:
    1.  Activar "Modo Desarrollador" en Configuración de Windows.
    2.  O ejecutar la terminal (VS Code / PowerShell) como **Administrador**.

### 3. 📱 Permisos
Asegúrate de que `android/app/src/main/AndroidManifest.xml` tenga:
```xml
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.USE_BIOMETRIC"/>
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/> <!-- Android 13+ -->
```

## 🚀 Comandos Útiles

```bash
# Limpiar caché de compilación (resuelve el 90% de errores raros)
flutter clean

# Instalar dependencias
flutter pub get

# Correr en dispositivo
flutter run

# Compilar APK para producción
flutter build apk --release
```

---

## 🤖 Sistema de Notificaciones Automáticas (Backend Python/Django)

Hemos implementado un sistema "inteligente" que avisa a los docentes minutos antes de su clase.

### 1. Requisitos Previos
*   **Token FCM**: La App móvil envía automáticamente el token del celular al Backend al iniciar sesión.
*   **Credenciales**: Se requiere el archivo `serviceAccountKey.json` (generado en Firebase Console -> Service Accounts) ubicado en `gestion_docentes/`.
*   **Librería**: `firebase-admin` (ya incluida en `requirements.txt`).

### 2. Script de Alertas
El script `core/management/commands/send_reminders.py`:
1.  Busca clases que inicien en los próximos **5 a 15 minutos**.
2.  Verifica si el docente **YA** marcó entrada (para no molestar).
3.  Si falta marcar, envía la notificación push.

### 3. Ejecución con Docker 🐳
Si usas Docker, esta es la forma de ejecutarlo o probarlo:

**Paso 1: Reconstruir (solo si agregaste nuevas librerías recientemente)**
```bash
docker-compose build
docker-compose up -d
```

**Paso 2: Ejecutar el Script Manualmente**
```bash
# Ejecutar comando dentro del contenedor 'web'
docker-compose exec web python manage.py send_reminders
```

**Paso 3: Automatización (Producción)**
Para que funcione solo, agrega una tarea al **CRON** del servidor (host) o usa una herramienta de tareas programadas que ejecute ese comando de Docker cada 10 minutos:
```cron
*/10 * * * * cd /ruta/a/SIGEDO && /usr/local/bin/docker-compose exec -T web python manage.py send_reminders >> /var/log/sigedo_cron.log 2>&1
```

---

## 🐳 Guía Rápida de Comandos Docker

Estos son los comandos esenciales para administrar el backend con Docker Compose.

### Iniciar y Detener
```bash
# Iniciar todo (Backend, BD, Redis, Nginx) en segundo plano
docker-compose up -d

# Reconstruir imágenes (necesario si editas requirements.txt o Dockerfile)
docker-compose up -d --build

# Detener todo
docker-compose down
```

### Gestión y Logs
```bash
# Ver logs en tiempo real (de todos los contenedores)
docker-compose logs -f

# Ver logs solo del backend (web)
docker-compose logs -f web

# Entrar a la terminal del contenedor web
docker-compose exec web bash
```

### Comandos de Django (dentro de Docker)
Para ejecutar comandos de `manage.py`, usa `docker-compose exec web`:

```bash
# Aplicar migraciones
docker-compose exec web python manage.py migrate

# Crear Superusuario
docker-compose exec web python manage.py createsuperuser

# Recopilar archivos estáticos
docker-compose exec web python manage.py collectstatic --noinput

# Ejecutar script de notificaciones manualmente
docker-compose exec web python manage.py send_reminders
```
