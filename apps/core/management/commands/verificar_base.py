from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection


class Command(BaseCommand):
    help = (
        "Comprueba con SELECT 1 que la base responde. Se ejecuta antes de "
        "migrate al arrancar para fallar rápido y con un mensaje claro."
    )

    def handle(self, *args, **options):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError as error:
            # Sin el mensaje original: puede incluir host, usuario o la URL.
            raise CommandError(
                "La base de datos no responde "
                f"(error_type={type(error).__name__}). Revisá que el proyecto "
                "de Supabase no esté pausado y que DATABASE_URL use el pooler "
                "en modo Session (*.pooler.supabase.com, puerto 5432)."
            ) from None
        self.stdout.write(self.style.SUCCESS("La base de datos responde."))
