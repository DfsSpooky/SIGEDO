import hashlib
import os
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.utils import timezone


ALLOWED_BACKUP_SUFFIXES = {".dump", ".backup", ".sql", ".sqlite3", ".db"}


class BackupError(Exception):
    pass


def _database_config():
    return settings.DATABASES["default"]


def _is_postgres():
    return _database_config()["ENGINE"].endswith("postgresql")


def _is_sqlite():
    return _database_config()["ENGINE"].endswith("sqlite3")


def _ensure_postgres_client_tools():
    missing = [
        binary
        for binary in ("pg_dump", "pg_restore", "psql")
        if shutil.which(binary) is None
    ]
    if missing:
        raise BackupError(
            "Faltan herramientas de PostgreSQL en el contenedor web: "
            + ", ".join(missing)
        )


def _pg_env():
    cfg = _database_config()
    env = os.environ.copy()
    if cfg.get("HOST"):
        env["PGHOST"] = str(cfg["HOST"])
    if cfg.get("PORT"):
        env["PGPORT"] = str(cfg["PORT"])
    if cfg.get("USER"):
        env["PGUSER"] = str(cfg["USER"])
    if cfg.get("PASSWORD"):
        env["PGPASSWORD"] = str(cfg["PASSWORD"])
    return env


def _run_command(command, env=None):
    result = subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise BackupError((result.stderr or result.stdout or "Error desconocido").strip())
    return (result.stdout or "") + (result.stderr or "")


def _quote_ident(value):
    return '"' + str(value).replace('"', '""') + '"'


def detect_backup_format(path):
    suffix = Path(path).suffix.lower()
    if suffix in {".dump", ".backup"}:
        return "POSTGRES_CUSTOM"
    if suffix == ".sql":
        return "POSTGRES_PLAIN"
    if suffix in {".sqlite3", ".db"}:
        return "SQLITE"
    return "DESCONOCIDO"


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hydrate_backup_metadata(respaldo):
    if not respaldo.archivo:
        return respaldo

    path = Path(respaldo.archivo.path)
    if not path.exists():
        raise BackupError(f"El archivo de respaldo no existe: {path}")

    respaldo.tamano_bytes = path.stat().st_size
    respaldo.checksum_sha256 = sha256_file(path)
    respaldo.formato = detect_backup_format(path)
    return respaldo


def _generated_backup_relative_path(nombre_base, extension):
    timestamp = timezone.now()
    safe_name = "".join(
        c if c.isalnum() or c in {"-", "_"} else "-" for c in nombre_base.lower()
    ).strip("-") or "respaldo"
    unique = timestamp.strftime("%H%M%S")
    return Path("backups") / timestamp.strftime("%Y/%m/%d") / f"{unique}_{safe_name}{extension}"


def create_system_backup(*, created_by=None, nombre=None, descripcion="", origen="GENERADO"):
    from core.models import RespaldoSistema

    timestamp = timezone.now()
    nombre = nombre or f"respaldo_{timestamp:%Y%m%d_%H%M%S}"

    if _is_postgres():
        _ensure_postgres_client_tools()
        extension = ".dump"
        formato = "POSTGRES_CUSTOM"
    elif _is_sqlite():
        extension = ".sqlite3"
        formato = "SQLITE"
    else:
        raise BackupError("Motor de base de datos no soportado para respaldos.")

    relative_path = _generated_backup_relative_path(nombre, extension)
    absolute_path = Path(settings.MEDIA_ROOT) / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)

    if _is_postgres():
        cfg = _database_config()
        _run_command(
            [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                "--file",
                str(absolute_path),
                str(cfg["NAME"]),
            ],
            env=_pg_env(),
        )
    else:
        cfg = _database_config()
        shutil.copy2(cfg["NAME"], absolute_path)

    respaldo = RespaldoSistema(
        nombre=nombre,
        descripcion=descripcion,
        archivo=str(relative_path),
        origen=origen,
        formato=formato,
        estado="DISPONIBLE",
        creado_por=created_by,
    )
    hydrate_backup_metadata(respaldo)
    respaldo.save()
    return respaldo


def synchronize_backup_index():
    from core.models import RespaldoSistema

    backup_root = Path(settings.MEDIA_ROOT) / "backups"
    synchronized = []
    if not backup_root.exists():
        return synchronized

    known_by_path = {
        item.archivo.name: item for item in RespaldoSistema.objects.all() if item.archivo
    }

    for path in backup_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_BACKUP_SUFFIXES:
            continue

        relative_name = str(path.relative_to(settings.MEDIA_ROOT))
        respaldo = known_by_path.get(relative_name)
        if respaldo is None:
            respaldo = RespaldoSistema(
                nombre=path.stem,
                descripcion="Registro sincronizado automaticamente desde almacenamiento.",
                archivo=relative_name,
                origen="SINCRONIZADO",
                estado="DISPONIBLE",
            )

        hydrate_backup_metadata(respaldo)
        respaldo.save()
        synchronized.append(respaldo)

    return synchronized


def _restore_postgres_file(backup_path):
    cfg = _database_config()
    env = _pg_env()
    maintenance_db = "postgres"
    db_name = str(cfg["NAME"])
    db_user = str(cfg["USER"])

    connections.close_all()

    terminate_sql = (
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid();"
    )
    _run_command(
        ["psql", "-v", "ON_ERROR_STOP=1", "-d", maintenance_db, "-c", terminate_sql],
        env=env,
    )
    _run_command(
        ["psql", "-v", "ON_ERROR_STOP=1", "-d", maintenance_db, "-c", f"DROP DATABASE IF EXISTS {_quote_ident(db_name)};"],
        env=env,
    )
    _run_command(
        ["psql", "-v", "ON_ERROR_STOP=1", "-d", maintenance_db, "-c", f"CREATE DATABASE {_quote_ident(db_name)} OWNER {_quote_ident(db_user)};"],
        env=env,
    )

    formato = detect_backup_format(backup_path)
    if formato == "POSTGRES_CUSTOM":
        _run_command(
            [
                "pg_restore",
                "--no-owner",
                "--no-privileges",
                "--dbname",
                db_name,
                str(backup_path),
            ],
            env=env,
        )
    elif formato == "POSTGRES_PLAIN":
        _run_command(
            [
                "psql",
                "-v",
                "ON_ERROR_STOP=1",
                "-d",
                db_name,
                "-f",
                str(backup_path),
            ],
            env=env,
        )
    else:
        raise BackupError("El archivo no es un respaldo PostgreSQL valido.")


def _restore_sqlite_file(backup_path):
    cfg = _database_config()
    db_path = Path(cfg["NAME"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connections.close_all()
    shutil.copy2(backup_path, db_path)


def restore_system_backup(respaldo, *, restored_by=None):
    from core.models import RespaldoSistema

    if not respaldo.archivo:
        raise BackupError("El respaldo no tiene archivo asociado.")

    backup_path = Path(respaldo.archivo.path)
    if not backup_path.exists():
        raise BackupError("El archivo del respaldo no existe en almacenamiento.")

    pre_restore = create_system_backup(
        created_by=restored_by,
        nombre=f"pre_restore_{timezone.now():%Y%m%d_%H%M%S}",
        descripcion=f"Respaldo automatico previo a restaurar {respaldo.nombre}.",
        origen="PRE_RESTORE",
    )

    respaldo.estado = "RESTAURANDO"
    respaldo.log_restauracion = ""
    respaldo.save(update_fields=["estado", "log_restauracion", "fecha_actualizacion"])

    try:
        if _is_postgres():
            _ensure_postgres_client_tools()
            _restore_postgres_file(backup_path)
        elif _is_sqlite():
            _restore_sqlite_file(backup_path)
        else:
            raise BackupError("Motor de base de datos no soportado para restauracion.")

        connections.close_all()
        call_command("migrate", interactive=False, verbosity=0)
        synchronize_backup_index()

        refreshed = (
            RespaldoSistema.objects.filter(checksum_sha256=sha256_file(backup_path))
            .order_by("-fecha_creacion")
            .first()
        )
        if refreshed is None:
            refreshed = respaldo

        pre_restore_refreshed = (
            RespaldoSistema.objects.filter(checksum_sha256=pre_restore.checksum_sha256)
            .order_by("-fecha_creacion")
            .first()
        )

        refreshed.estado = "RESTAURADO"
        refreshed.restaurado_por = restored_by
        refreshed.respaldo_previo = pre_restore_refreshed
        refreshed.fecha_restauracion = timezone.now()
        refreshed.log_restauracion = "Restauracion completada correctamente."
        refreshed.save()
        return refreshed, pre_restore_refreshed
    except Exception as exc:
        try:
            failed = (
                RespaldoSistema.objects.filter(checksum_sha256=respaldo.checksum_sha256)
                .order_by("-fecha_creacion")
                .first()
            )
            if failed:
                failed.estado = "ERROR"
                failed.log_restauracion = str(exc)
                failed.save()
        except Exception:
            pass
        raise
