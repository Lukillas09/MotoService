from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import (
    IntegrityError,
    close_old_connections,
    connection,
    transaction,
)
from django.test import TestCase, TransactionTestCase

from apps.usuarios.services import (
    actualizar_usuario,
    crear_usuario_invitado,
)


class EmailNormalizadoConstraintTests(TestCase):
    def test_base_rechaza_duplicado_exacto(self):
        User = get_user_model()
        User.objects.create_user(username="primero", email="usuario@example.com")

        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username="segundo", email="usuario@example.com")

    def test_base_rechaza_mayusculas_y_espacios_externos(self):
        User = get_user_model()
        User.objects.create_user(
            username="primero",
            email=" Usuario@Example.com ",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                username="segundo",
                email="usuario@example.com",
            )

    def test_base_permite_varios_emails_vacios_historicos(self):
        User = get_user_model()
        User.objects.create_user(username="primero", email="")
        User.objects.create_user(username="segundo", email="")
        User.objects.create_user(username="tercero", email="   ")
        User.objects.create_user(username="cuarto", email=" ")

        self.assertEqual(User.objects.count(), 4)

    def test_creacion_convierte_carrera_en_error_amigable(self):
        get_user_model().objects.create_user(
            username="existente",
            email="ocupado@example.com",
        )
        datos = {
            "username": "nuevo",
            "first_name": "Nuevo",
            "last_name": "Usuario",
            "email": " OCUPADO@example.com ",
            "rol": "USUARIO",
        }

        with patch(
            "apps.usuarios.services.validar_email_unico",
            return_value=None,
        ), self.assertRaises(ValidationError) as contexto:
            crear_usuario_invitado(datos)

        self.assertEqual(
            contexto.exception.message_dict["email"],
            ["Ya existe un usuario con este correo electrónico."],
        )
        self.assertFalse(get_user_model().objects.filter(username="nuevo").exists())

    def test_edicion_convierte_carrera_en_error_amigable(self):
        User = get_user_model()
        actor = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="clave-segura",
        )
        objetivo = User.objects.create_user(
            username="objetivo",
            email="objetivo@example.com",
        )
        User.objects.create_user(username="ocupado", email="ocupado@example.com")
        datos = {
            "username": "objetivo",
            "first_name": "Objetivo",
            "last_name": "Demo",
            "email": " OCUPADO@example.com ",
            "rol": "USUARIO",
        }

        with patch(
            "apps.usuarios.services.validar_email_unico",
            return_value=None,
        ), self.assertRaises(ValidationError) as contexto:
            actualizar_usuario(actor, objetivo, datos)

        self.assertEqual(
            contexto.exception.message_dict["email"],
            ["Ya existe un usuario con este correo electrónico."],
        )
        objetivo.refresh_from_db()
        self.assertEqual(objetivo.email, "objetivo@example.com")


class EmailNormalizadoMigrationSafetyTests(TransactionTestCase):
    reset_sequences = True

    def test_preflight_aborta_sin_modificar_usuarios_duplicados(self):
        migracion = import_module(
            "apps.usuarios.migrations.0001_email_normalizado_unico"
        )
        with connection.schema_editor() as schema_editor:
            migracion.eliminar_indice_email_normalizado(apps, schema_editor)

        User = get_user_model()
        User.objects.create_user(
            username="primero",
            email=" Duplicado@example.com ",
        )
        User.objects.create_user(
            username="segundo",
            email="duplicado@example.com",
        )

        try:
            with self.assertRaises(RuntimeError) as contexto:
                with connection.schema_editor() as schema_editor:
                    migracion.crear_indice_email_normalizado(apps, schema_editor)

            self.assertEqual(User.objects.count(), 2)
            self.assertNotIn(
                "duplicado@example.com",
                str(contexto.exception).lower(),
            )
        finally:
            User.objects.filter(username="segundo").delete()
            with connection.schema_editor() as schema_editor:
                migracion.crear_indice_email_normalizado(apps, schema_editor)


@skipUnless(
    connection.vendor == "postgresql",
    "La carrera real del índice único requiere PostgreSQL.",
)
class EmailNormalizadoConcurrencyPostgreSQLTests(TransactionTestCase):
    reset_sequences = True

    def test_dos_inserciones_concurrentes_dejan_un_solo_email_normalizado(self):
        barrera = Barrier(2)

        def crear(username, email):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                try:
                    with transaction.atomic():
                        get_user_model().objects.create_user(
                            username=username,
                            email=email,
                        )
                except IntegrityError:
                    return "duplicado"
                return "creado"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = tuple(
                executor.map(
                    lambda datos: crear(*datos),
                    (
                        ("primero", " Usuario@example.com "),
                        ("segundo", "usuario@example.com"),
                    ),
                )
            )

        self.assertCountEqual(resultados, ("creado", "duplicado"))
        self.assertEqual(get_user_model().objects.count(), 1)
