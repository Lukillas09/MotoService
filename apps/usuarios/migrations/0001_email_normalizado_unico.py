from django.db import migrations
from django.db.models import Count
from django.db.models.functions import Lower, Trim


INDEX_NAME = "usuarios_user_email_normalizado_uniq"


def crear_indice_email_normalizado(apps, schema_editor):
    User = apps.get_model("auth", "User")
    alias = schema_editor.connection.alias
    vendor = schema_editor.connection.vendor
    tabla = schema_editor.quote_name(User._meta.db_table)
    indice = schema_editor.quote_name(INDEX_NAME)

    if vendor == "postgresql":
        # Evita que aparezca un duplicado entre el preflight y el CREATE INDEX.
        schema_editor.execute(f"LOCK TABLE {tabla} IN SHARE ROW EXCLUSIVE MODE")
    elif vendor != "sqlite":
        raise RuntimeError(
            "La unicidad normalizada de email requiere PostgreSQL. "
            "SQLite sólo está admitido para desarrollo y tests."
        )

    duplicados = (
        User.objects.using(alias)
        .annotate(email_normalizado=Lower(Trim("email")))
        .exclude(email_normalizado="")
        .exclude(email_normalizado__isnull=True)
        .values("email_normalizado")
        .annotate(total=Count("pk"))
        .filter(total__gt=1)
        .count()
    )
    if duplicados:
        raise RuntimeError(
            "No se puede garantizar la unicidad de email: existen "
            f"{duplicados} grupo(s) de usuarios con emails normalizados duplicados. "
            "Corregí esos datos manualmente y volvé a ejecutar la migración; "
            "ninguna cuenta fue eliminada ni fusionada."
        )

    schema_editor.execute(
        f"CREATE UNIQUE INDEX {indice} ON {tabla} "
        "(LOWER(TRIM(email))) WHERE TRIM(email) <> ''"
    )


def eliminar_indice_email_normalizado(apps, schema_editor):
    indice = schema_editor.quote_name(INDEX_NAME)
    schema_editor.execute(f"DROP INDEX {indice}")


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(
            crear_indice_email_normalizado,
            eliminar_indice_email_normalizado,
        ),
    ]
