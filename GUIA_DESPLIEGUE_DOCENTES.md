# Guía de Despliegue (Solo Sistema + Docentes)

## Objetivo
Dejar el sistema con:
- Datos base de la institución
- Docentes importados desde Excel
- Sin cursos importados

---

## Opción A: Sin Docker

1. Aplicar migraciones:

```bash
python manage.py migrate
```

2. Configurar datos del sistema (limpia y crea estructura institucional):

```bash
python manage.py configurar_institucion
```

3. Importar solo docentes desde Excel:

```bash
python manage.py crear_docentes_desde_excel --archivo "HORARIO DE CLASES 2026-A.xlsx"
```

4. Verificar duplicados:

```bash
python manage.py verificar_duplicados_docentes
```

---

## Opción B: Con Docker Compose

1. Aplicar migraciones:

```bash
docker compose exec web python manage.py migrate
```

2. Configurar datos del sistema:

```bash
docker compose exec web python manage.py configurar_institucion
```

3. Importar solo docentes desde Excel:

```bash
docker compose exec web python manage.py crear_docentes_desde_excel --archivo "HORARIO DE CLASES 2026-A.xlsx"
```

4. Verificar duplicados:

```bash
docker compose exec web python manage.py verificar_duplicados_docentes
```

---

## Importante
- **No ejecutar** `importar_malla_curricular` si solo quieres docentes y cero cursos.
- El archivo Excel debe estar accesible en `data_temp/` (o pasar ruta absoluta con `--archivo`).
