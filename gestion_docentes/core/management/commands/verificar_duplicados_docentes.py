from collections import defaultdict

from django.core.management.base import BaseCommand

from core.models.users import Docente
from core.utils.docente_identity import normalize_docente_key


class Command(BaseCommand):
    help = "Verifica docentes duplicados por identidad canónica."

    def handle(self, *args, **kwargs):
        groups = defaultdict(list)
        qs = Docente.objects.filter(is_staff=False, is_superuser=False).order_by("id")

        for d in qs:
            full_name = " ".join(p for p in [d.first_name, d.last_name] if p).strip() or d.username
            key = normalize_docente_key(full_name)
            if key:
                groups[key].append(d)

        duplicates = {k: v for k, v in groups.items() if len(v) > 1}

        self.stdout.write(f"Docentes no admin: {qs.count()}")
        self.stdout.write(f"Grupos duplicados detectados: {len(duplicates)}")

        for key, docs in sorted(duplicates.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            self.stdout.write(f"\n{key} ({len(docs)})")
            for d in docs:
                nombre = " ".join(p for p in [d.first_name, d.last_name] if p).strip()
                self.stdout.write(f"  - id={d.id} username={d.username} nombre={nombre}")
