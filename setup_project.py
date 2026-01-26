import subprocess
import time
import sys

def run_command(command, description):
    print(f"--- {description} ---")
    try:
        result = subprocess.run(command, shell=True, check=True, text=True)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error executing: {description}")
        print(e)
        sys.exit(1)

def main():
    # 1. Start Docker containers
    run_command("docker-compose up -d --build", "Loteando contenedores Docker")

    # 2. Wait for DB to be ready (simplified wait, could be more robust)
    print("Esperando a que la base de datos esté lista...")
    time.sleep(10)

    # 3. Run migrations
    run_command("docker-compose exec -T web python manage.py migrate", "Ejecutando migraciones")

    # 4. Collect static files
    run_command("docker-compose exec -T web python manage.py collectstatic --noinput", "Recolectando archivos estáticos")

    # 5. Create superuser
    create_superuser_cmd = (
        "docker-compose exec -T web python manage.py shell -c "
        "\"from django.contrib.auth import get_user_model; "
        "User = get_user_model(); "
        "print('Superusuario miguel creado exitosamente') if (not User.objects.filter(username='miguel').exists() and "
        "User.objects.create_superuser('miguel', 'miguel@example.com', 'teng90%')) "
        "else print('El superusuario miguel ya existe')\""
    )
    run_command(create_superuser_cmd, "Configurando superusuario")

    print("\n¡Configuración completada con éxito!")
    print("Puedes acceder a la aplicación en http://localhost")

if __name__ == "__main__":
    main()
