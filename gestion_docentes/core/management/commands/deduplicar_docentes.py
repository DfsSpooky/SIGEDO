import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from core.models.users import Docente
from core.utils.docente_identity import normalize_docente_key


class Command(BaseCommand):
    help = "Consolida docentes duplicados por clave canónica de nombre."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica cambios. Sin este flag solo muestra vista previa.",
        )

    @staticmethod
    def _username_score(username):
        # Preferimos username sin sufijo numérico y luego el más corto.
        return (1 if re.search(r"\d+$", username or "") else 0, len(username or ""), username or "")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        qs = Docente.objects.filter(is_staff=False, is_superuser=False).order_by("id")

        groups = defaultdict(list)
        for docente in qs:
            full_name = " ".join(
                p for p in [docente.first_name, docente.last_name] if p
            ).strip() or docente.username
            key = normalize_docente_key(full_name)
            if key:
                groups[key].append(docente)

        duplicates = {k: v for k, v in groups.items() if len(v) > 1}
        self.stdout.write(self.style.WARNING(f"Modo apply: {apply_changes}"))
        self.stdout.write(f"Docentes no admin: {qs.count()}")
        self.stdout.write(f"Grupos duplicados detectados: {len(duplicates)}")

        merges = 0
        removed = 0
        moved_relations = 0

        with transaction.atomic():
            for key, docs in sorted(duplicates.items(), key=lambda kv: (-len(kv[1]), kv[0])):
                canonical = sorted(docs, key=lambda d: (self._username_score(d.username), d.id))[0]
                dupes = [d for d in docs if d.id != canonical.id]

                self.stdout.write(
                    f"\nGrupo {key}: canónico id={canonical.id} user={canonical.username} total={len(docs)}"
                )

                for dup in dupes:
                    self.stdout.write(f"  - {'Fusionando' if apply_changes else 'Plan'} id={dup.id} user={dup.username}")

                    if apply_changes:
                        canonical.especialidades.add(*dup.especialidades.all())
                        canonical.groups.add(*dup.groups.all())
                        canonical.user_permissions.add(*dup.user_permissions.all())

                        for rel in Docente._meta.related_objects:
                            accessor = rel.get_accessor_name()
                            if not accessor:
                                continue

                            if rel.one_to_many:
                                field_name = rel.field.name
                                manager = getattr(dup, accessor)
                                for obj in manager.all():
                                    setattr(obj, field_name, canonical)
                                    try:
                                        obj.save(update_fields=[field_name])
                                        moved_relations += 1
                                    except IntegrityError:
                                        obj.delete()
                            elif rel.many_to_many and rel.auto_created:
                                manager_dup = getattr(dup, accessor)
                                manager_can = getattr(canonical, accessor)
                                items = list(manager_dup.all())
                                if items:
                                    manager_can.add(*items)
                                    moved_relations += len(items)

                        dup.delete()
                        removed += 1

                    merges += 1

            if not apply_changes:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("\nResumen:"))
        self.stdout.write(f"  fusiones {'ejecutadas' if apply_changes else 'planificadas'}: {merges}")
        self.stdout.write(f"  docentes {'eliminados' if apply_changes else 'a eliminar'}: {removed if apply_changes else merges}")
        self.stdout.write(f"  relaciones {'movidas' if apply_changes else 'a mover'}: {moved_relations}")
