from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.usuarios.models import LimiteAutenticacion


class Command(BaseCommand):
    help = "Elimina contadores de autenticación cuya ventana ya venció."

    def handle(self, *args, **options):
        eliminados, _detalle = LimiteAutenticacion.objects.filter(
            expira_en__lte=timezone.now()
        ).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Se eliminaron {eliminados} límites de autenticación vencidos."
            )
        )
