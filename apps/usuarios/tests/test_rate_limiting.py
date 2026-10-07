from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import OperationalError, connection, connections
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from apps.usuarios.models import LimiteAutenticacion
from apps.usuarios.rate_limiting import (
    ReglaLimite,
    consumir_limites,
    obtener_ip_cliente,
)
from config.settings.base import env_positive_int


@override_settings(
    AUTH_LOGIN_IP_MAX_ATTEMPTS=20,
    AUTH_LOGIN_IDENTIFIER_MAX_ATTEMPTS=10,
    AUTH_LOGIN_WINDOW_SECONDS=900,
    PASSWORD_RESET_IP_MAX_ATTEMPTS=10,
    PASSWORD_RESET_IDENTIFIER_MAX_ATTEMPTS=5,
    PASSWORD_RESET_WINDOW_SECONDS=3600,
)
class RateLimitingAutenticacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="lucas",
            password="Clave-segura-123",
            email="lucas@example.com",
            is_active=True,
        )
        cls.superuser = get_user_model().objects.create_superuser(
            username="admin-rate-limit",
            password="Clave-admin-segura-123",
            email="admin-rate-limit@example.com",
        )

    def login(self, *, username="lucas", password="incorrecta", ip="198.51.100.10"):
        return self.client.post(
            reverse("login"),
            {"username": username, "password": password},
            REMOTE_ADDR=ip,
        )

    def password_reset(self, email, *, ip="198.51.100.10"):
        return self.client.post(
            reverse("password_reset"),
            {"email": email},
            REMOTE_ADDR=ip,
        )

    def admin_login(
        self,
        *,
        username="admin-rate-limit",
        password="incorrecta",
        ip="198.51.100.10",
    ):
        return self.client.post(
            reverse("admin:login"),
            {
                "username": username,
                "password": password,
                "next": reverse("admin:index"),
            },
            REMOTE_ADDR=ip,
        )

    @override_settings(
        AUTH_LOGIN_IP_MAX_ATTEMPTS=50,
        AUTH_LOGIN_IDENTIFIER_MAX_ATTEMPTS=2,
        AUTH_LOGIN_WINDOW_SECONDS=300,
    )
    def test_login_limita_por_identificador_normalizado(self):
        self.assertEqual(self.login(username="  ＬＵＣＡＳ  ").status_code, 200)
        self.assertEqual(self.login(username="lucas").status_code, 200)

        response = self.login(username="LuCaS")

        self.assertEqual(response.status_code, 429)
        self.assertGreaterEqual(int(response.headers["Retry-After"]), 1)
        self.assertLessEqual(int(response.headers["Retry-After"]), 300)
        self.assertContains(
            response,
            "demasiados intentos",
            status_code=429,
        )
        self.assertNotContains(response, "lucas", status_code=429)
        self.assertNotContains(response, "incorrecta", status_code=429)
        self.assertIn("no-store", response.headers["Cache-Control"])

        limite = LimiteAutenticacion.objects.get(
            ambito=LimiteAutenticacion.Ambito.LOGIN_IDENTIFICADOR
        )
        self.assertEqual(limite.intentos, 2)

    @override_settings(
        AUTH_LOGIN_IP_MAX_ATTEMPTS=2,
        AUTH_LOGIN_IDENTIFIER_MAX_ATTEMPTS=50,
    )
    def test_login_limita_por_ip_y_no_crea_identidades_despues_del_bloqueo(self):
        self.assertEqual(self.login(username="usuario-1").status_code, 200)
        self.assertEqual(self.login(username="usuario-2").status_code, 200)

        response = self.login(username="usuario-3")

        self.assertEqual(response.status_code, 429)
        self.assertEqual(
            LimiteAutenticacion.objects.filter(
                ambito=LimiteAutenticacion.Ambito.LOGIN_IDENTIFICADOR
            ).count(),
            2,
        )
        limite_ip = LimiteAutenticacion.objects.get(
            ambito=LimiteAutenticacion.Ambito.LOGIN_IP
        )
        self.assertEqual(limite_ip.intentos, 2)

    def test_login_exitoso_devuelve_solo_sus_reservas(self):
        response = self.login(password="Clave-segura-123")

        self.assertRedirects(response, reverse("core:dashboard"))
        self.assertEqual(
            set(LimiteAutenticacion.objects.values_list("intentos", flat=True)),
            {0},
        )

    @override_settings(
        AUTH_LOGIN_IP_MAX_ATTEMPTS=50,
        AUTH_LOGIN_IDENTIFIER_MAX_ATTEMPTS=2,
        AUTH_LOGIN_WINDOW_SECONDS=300,
    )
    def test_login_admin_reutiliza_el_limite_por_identificador(self):
        from apps.usuarios.views import login_admin_protegido

        self.assertEqual(resolve(reverse("admin:login")).func, login_admin_protegido)
        self.assertEqual(self.admin_login().status_code, 200)
        self.assertEqual(self.admin_login().status_code, 200)

        response = self.admin_login()

        self.assertEqual(response.status_code, 429)
        self.assertGreaterEqual(int(response.headers["Retry-After"]), 1)
        self.assertLessEqual(int(response.headers["Retry-After"]), 300)
        self.assertNotContains(
            response,
            "admin-rate-limit",
            status_code=429,
        )

    def test_login_admin_exitoso_devuelve_solo_sus_reservas(self):
        response = self.admin_login(password="Clave-admin-segura-123")

        self.assertRedirects(response, reverse("admin:index"))
        self.assertEqual(
            set(LimiteAutenticacion.objects.values_list("intentos", flat=True)),
            {0},
        )

    @override_settings(
        AUTH_LOGIN_IP_MAX_ATTEMPTS=2,
        AUTH_LOGIN_IDENTIFIER_MAX_ATTEMPTS=2,
        AUTH_LOGIN_WINDOW_SECONDS=300,
    )
    def test_login_valido_funciona_al_vencer_la_ventana(self):
        self.login()
        self.login()
        self.assertEqual(self.login().status_code, 429)
        LimiteAutenticacion.objects.update(
            expira_en=timezone.now() - timedelta(seconds=1)
        )

        response = self.login(password="Clave-segura-123")

        self.assertRedirects(response, reverse("core:dashboard"))
        self.assertFalse(
            LimiteAutenticacion.objects.exclude(intentos=0).exists()
        )

    @override_settings(
        PASSWORD_RESET_IP_MAX_ATTEMPTS=50,
        PASSWORD_RESET_IDENTIFIER_MAX_ATTEMPTS=2,
        PASSWORD_RESET_WINDOW_SECONDS=600,
    )
    def test_password_reset_limita_email_sin_revelar_existencia(self):
        self.assertEqual(
            self.password_reset("LUCAS@example.com").status_code,
            302,
        )
        self.assertEqual(
            self.password_reset(" lucas@example.com ").status_code,
            302,
        )
        self.assertEqual(len(mail.outbox), 2)

        response = self.password_reset("lucas@example.com")

        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(mail.outbox), 2)
        self.assertNotContains(response, "lucas@example.com", status_code=429)
        self.assertLessEqual(int(response.headers["Retry-After"]), 600)

    @override_settings(
        PASSWORD_RESET_IP_MAX_ATTEMPTS=50,
        PASSWORD_RESET_IDENTIFIER_MAX_ATTEMPTS=1,
    )
    def test_respuesta_bloqueada_es_igual_para_email_existente_e_inexistente(self):
        self.password_reset("lucas@example.com", ip="198.51.100.20")
        existente = self.password_reset(
            "lucas@example.com", ip="198.51.100.20"
        )
        self.password_reset("nadie@example.com", ip="198.51.100.21")
        inexistente = self.password_reset(
            "nadie@example.com", ip="198.51.100.21"
        )

        self.assertEqual(existente.status_code, 429)
        self.assertEqual(inexistente.status_code, 429)
        self.assertEqual(existente.content, inexistente.content)

    @override_settings(
        PASSWORD_RESET_IP_MAX_ATTEMPTS=2,
        PASSWORD_RESET_IDENTIFIER_MAX_ATTEMPTS=50,
    )
    def test_password_reset_limita_por_ip(self):
        self.password_reset("uno@example.com")
        self.password_reset("dos@example.com")

        response = self.password_reset("tres@example.com")

        self.assertEqual(response.status_code, 429)
        self.assertEqual(
            LimiteAutenticacion.objects.filter(
                ambito=LimiteAutenticacion.Ambito.PASSWORD_RESET_EMAIL
            ).count(),
            2,
        )

    def test_sujetos_persistidos_no_contienen_datos_en_claro(self):
        self.login(username="Identidad.Secreta")
        self.password_reset("Correo.Secreto@example.com", ip="203.0.113.45")

        hashes = list(
            LimiteAutenticacion.objects.values_list("sujeto_hash", flat=True)
        )
        self.assertTrue(hashes)
        for sujeto_hash in hashes:
            self.assertEqual(len(sujeto_hash), 64)
            self.assertNotIn("identidad", sujeto_hash.lower())
            self.assertNotIn("correo", sujeto_hash.lower())
            self.assertNotIn("203.0.113.45", sujeto_hash)

    def test_fallo_de_base_devuelve_503_neutro_sin_fail_open(self):
        casos = (
            (
                "apps.usuarios.views.consumir_login",
                reverse("login"),
                {"username": "lucas", "password": "Clave-segura-123"},
            ),
            (
                "apps.usuarios.views.consumir_password_reset",
                reverse("password_reset"),
                {"email": "lucas@example.com"},
            ),
            (
                "apps.usuarios.views.consumir_login",
                reverse("admin:login"),
                {
                    "username": "admin-rate-limit",
                    "password": "Clave-admin-segura-123",
                },
            ),
        )
        for objetivo, ruta, datos in casos:
            with self.subTest(ruta=ruta):
                self.client.logout()
                with patch(
                    objetivo,
                    side_effect=OperationalError(
                        "detalle lucas@example.com Clave-segura-123"
                    ),
                ):
                    with self.assertLogs(
                        "apps.usuarios.views", level="ERROR"
                    ) as logs:
                        response = self.client.post(ruta, datos)

                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.headers["Retry-After"], "60")
                self.assertNotContains(
                    response,
                    "lucas@example.com",
                    status_code=503,
                )
                self.assertNotContains(
                    response,
                    "Clave-segura-123",
                    status_code=503,
                )
                self.assertNotIn("lucas@example.com", logs.output[0])
                self.assertNotIn("Clave-segura-123", logs.output[0])

        self.assertEqual(len(mail.outbox), 0)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_convierte_error_de_sesion_previo_al_post_en_503(self):
        with patch(
            "django.contrib.auth.middleware.get_user",
            side_effect=OperationalError(
                "detalle lucas@example.com Clave-segura-123"
            ),
        ):
            with self.assertLogs("apps.usuarios.views", level="ERROR") as logs:
                response = self.login(password="Clave-segura-123")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Retry-After"], "60")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertNotIn("lucas@example.com", logs.output[0])
        self.assertNotIn("Clave-segura-123", logs.output[0])
        self.assertFalse(LimiteAutenticacion.objects.exists())

    def test_recuperacion_marca_el_email_como_parametro_sensible(self):
        parametros_sensibles = []

        def fallar(request):
            parametros_sensibles.append(request.sensitive_post_parameters)
            raise OperationalError("base no disponible")

        with patch(
            "apps.usuarios.views.consumir_password_reset",
            side_effect=fallar,
        ):
            with self.assertLogs("apps.usuarios.views", level="ERROR"):
                response = self.password_reset("lucas@example.com")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(parametros_sensibles, ["__ALL__"])

    @override_settings(AUTH_RATE_LIMIT_CLIENT_IP_META_KEY="HTTP_X_REAL_IP")
    def test_ip_de_railway_se_valida_y_agrupa_ipv6_por_64(self):
        factory = RequestFactory()
        primera = factory.post(
            reverse("login"),
            HTTP_X_REAL_IP="2001:db8:abcd:12::1",
            REMOTE_ADDR="198.51.100.1",
        )
        segunda = factory.post(
            reverse("login"),
            HTTP_X_REAL_IP="2001:db8:abcd:12::ffff",
            REMOTE_ADDR="198.51.100.2",
        )
        invalida = factory.post(
            reverse("login"),
            HTTP_X_REAL_IP="valor-invalido",
            REMOTE_ADDR="198.51.100.3",
        )

        self.assertEqual(obtener_ip_cliente(primera), "2001:db8:abcd:12::/64")
        self.assertEqual(obtener_ip_cliente(segunda), "2001:db8:abcd:12::/64")
        self.assertEqual(obtener_ip_cliente(invalida), "198.51.100.3")

    def test_ip_ausente_usa_un_sujeto_estable_en_lugar_de_omitir_el_limite(self):
        request = RequestFactory().post(reverse("login"))
        request.META.pop("REMOTE_ADDR", None)

        self.assertEqual(obtener_ip_cliente(request), "ip-desconocida")

    def test_comando_elimina_solo_limites_vencidos(self):
        ahora = timezone.now()
        comunes = {
            "ambito": LimiteAutenticacion.Ambito.LOGIN_IP,
            "ventana_iniciada_en": ahora - timedelta(hours=1),
            "intentos": 1,
        }
        LimiteAutenticacion.objects.create(
            **comunes,
            sujeto_hash="a" * 64,
            expira_en=ahora - timedelta(seconds=1),
        )
        activo = LimiteAutenticacion.objects.create(
            **comunes,
            sujeto_hash="b" * 64,
            expira_en=ahora + timedelta(minutes=5),
        )
        salida = StringIO()

        call_command("limpiar_limites_autenticacion", stdout=salida)

        self.assertEqual(
            list(LimiteAutenticacion.objects.values_list("pk", flat=True)),
            [activo.pk],
        )
        self.assertIn("1 límites", salida.getvalue())

    def test_configuracion_de_seguridad_es_positiva(self):
        for nombre in (
            "AUTH_LOGIN_IP_MAX_ATTEMPTS",
            "AUTH_LOGIN_IDENTIFIER_MAX_ATTEMPTS",
            "AUTH_LOGIN_WINDOW_SECONDS",
            "PASSWORD_RESET_IP_MAX_ATTEMPTS",
            "PASSWORD_RESET_IDENTIFIER_MAX_ATTEMPTS",
            "PASSWORD_RESET_WINDOW_SECONDS",
        ):
            with self.subTest(nombre=nombre):
                self.assertGreater(getattr(settings, nombre), 0)

    def test_configuracion_rechaza_limites_no_positivos(self):
        with patch.dict("os.environ", {"LIMITE_DE_PRUEBA": "0"}):
            with self.assertRaises(ImproperlyConfigured):
                env_positive_int("LIMITE_DE_PRUEBA", 1)


@skipUnless(
    connection.vendor == "postgresql",
    "La concurrencia real de select_for_update requiere PostgreSQL.",
)
class RateLimitingConcurrencyPostgreSQLTests(TransactionTestCase):
    reset_sequences = True

    def test_reservas_concurrentes_no_superan_el_maximo(self):
        trabajadores = 6
        max_intentos = 3
        barrera = Barrier(trabajadores)
        regla = ReglaLimite(
            ambito=LimiteAutenticacion.Ambito.LOGIN_IP,
            sujeto="198.51.100.80",
            max_intentos=max_intentos,
            ventana_segundos=300,
        )

        def consumir_en_hilo():
            connections.close_all()
            try:
                barrera.wait(timeout=10)
                return consumir_limites((regla,)).permitido
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=trabajadores) as executor:
            resultados = list(
                executor.map(lambda _indice: consumir_en_hilo(), range(trabajadores))
            )

        self.assertEqual(sum(resultados), max_intentos)
        limite = LimiteAutenticacion.objects.get(
            ambito=LimiteAutenticacion.Ambito.LOGIN_IP
        )
        self.assertEqual(limite.intentos, max_intentos)

    def _consumir_en_paralelo(self, reglas):
        barrera = Barrier(len(reglas))

        def consumir_en_hilo(reglas_del_hilo):
            connections.close_all()
            try:
                barrera.wait(timeout=10)
                return consumir_limites(reglas_del_hilo).permitido
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(reglas)) as executor:
            return list(executor.map(consumir_en_hilo, reglas))

    def test_misma_ip_e_identidades_distintas_respetan_el_maximo(self):
        trabajadores = 6
        max_intentos = 3
        reglas = []
        for indice in range(trabajadores):
            reglas.append(
                (
                    ReglaLimite(
                        ambito=LimiteAutenticacion.Ambito.LOGIN_IP,
                        sujeto="198.51.100.90",
                        max_intentos=max_intentos,
                        ventana_segundos=300,
                    ),
                    ReglaLimite(
                        ambito=LimiteAutenticacion.Ambito.LOGIN_IDENTIFICADOR,
                        sujeto=f"usuario-{indice}",
                        max_intentos=20,
                        ventana_segundos=300,
                    ),
                )
            )

        resultados = self._consumir_en_paralelo(reglas)

        self.assertEqual(sum(resultados), max_intentos)
        limite_ip = LimiteAutenticacion.objects.get(
            ambito=LimiteAutenticacion.Ambito.LOGIN_IP
        )
        self.assertEqual(limite_ip.intentos, max_intentos)

    def test_ips_distintas_y_misma_identidad_respetan_el_maximo(self):
        trabajadores = 6
        max_intentos = 3
        reglas = []
        for indice in range(trabajadores):
            reglas.append(
                (
                    ReglaLimite(
                        ambito=LimiteAutenticacion.Ambito.LOGIN_IP,
                        sujeto=f"198.51.100.{100 + indice}",
                        max_intentos=20,
                        ventana_segundos=300,
                    ),
                    ReglaLimite(
                        ambito=LimiteAutenticacion.Ambito.LOGIN_IDENTIFICADOR,
                        sujeto="identidad-compartida",
                        max_intentos=max_intentos,
                        ventana_segundos=300,
                    ),
                )
            )

        resultados = self._consumir_en_paralelo(reglas)

        self.assertEqual(sum(resultados), max_intentos)
        limite_identidad = LimiteAutenticacion.objects.get(
            ambito=LimiteAutenticacion.Ambito.LOGIN_IDENTIFICADOR
        )
        self.assertEqual(limite_identidad.intentos, max_intentos)
