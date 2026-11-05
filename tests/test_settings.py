import importlib.util
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import types
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse

from config.settings.base import env_bool


class DevelopmentStaticFilesTests(SimpleTestCase):
    def test_booleanos_reconocen_valores_explicitos_y_respetan_default(self):
        for value, default, expected in (
            (" True ", False, True),
            ("1", False, True),
            ("false", True, False),
            ("0", True, False),
            ("release", True, True),
            ("release", False, False),
        ):
            with self.subTest(value=value, default=default):
                with patch.dict(os.environ, {"TEST_BOOLEAN_SETTING": value}):
                    self.assertEqual(env_bool("TEST_BOOLEAN_SETTING", default), expected)

    def test_desarrollo_siempre_admite_hosts_locales(self):
        environment = os.environ.copy()
        environment.update(
            DJANGO_SETTINGS_MODULE="config.settings.development",
            ALLOWED_HOSTS="motoservice.onrender.com",
            DATABASE_URL="sqlite:///:memory:",
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import json
import django
django.setup()
from django.conf import settings
print(json.dumps(settings.ALLOWED_HOSTS))
""",
            ],
            cwd=Path(settings.BASE_DIR),
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        allowed_hosts = json.loads(result.stdout)

        self.assertIn("motoservice.onrender.com", allowed_hosts)
        self.assertIn("localhost", allowed_hosts)
        self.assertIn("127.0.0.1", allowed_hosts)

    def probe_runserver(self, django_debug=None, legacy_debug="release"):
        environment = os.environ.copy()
        environment.update(
            DJANGO_SETTINGS_MODULE="config.settings.development",
            DEBUG=legacy_debug,
            DJANGO_DEBUG=django_debug or "",
            DATABASE_URL="sqlite:///:memory:",
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import json
import django
django.setup()
from django.conf import settings
from django.contrib.staticfiles.management.commands.runserver import Command
from django.test import RequestFactory

handler = Command().get_handler(use_static_handler=True, insecure_serving=False)
responses = {}
for path in ('css/tokens.css', 'icons/ui.svg', 'icons/motoservice-mark-96.png'):
    headers = []
    request = RequestFactory().get('/static/' + path, HTTP_HOST='127.0.0.1')
    response = handler(request.environ, lambda status, values: headers.append((status, values)))
    try:
        body = b''.join(response)
        status, values = headers[0]
        responses[path] = {'status': status, 'content_type': dict(values)['Content-Type'], 'length': len(body)}
    finally:
        response.close()
print(json.dumps({'debug': settings.DEBUG, 'responses': responses}))
""",
            ],
            cwd=Path(settings.BASE_DIR),
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        # Con DEBUG=False el 404 de estáticos se registra en stdout antes del JSON.
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_runserver_sirve_css_iconos_e_imagenes_con_debug_release_heredado(self):
        result = self.probe_runserver()

        self.assertTrue(result["debug"])
        for path, content_type in (
            ("css/tokens.css", "text/css"),
            ("icons/ui.svg", "image/svg+xml"),
            ("icons/motoservice-mark-96.png", "image/png"),
        ):
            with self.subTest(path=path):
                response = result["responses"][path]
                self.assertEqual(response["status"], "200 OK")
                self.assertEqual(response["content_type"], content_type)
                self.assertGreater(response["length"], 0)

    def test_debug_false_explicito_se_respeta_y_django_debug_tiene_prioridad(self):
        for django_debug, legacy_debug, expected in (
            (None, "False", False),
            ("False", "True", False),
            ("True", "False", True),
        ):
            with self.subTest(django_debug=django_debug, legacy_debug=legacy_debug):
                result = self.probe_runserver(django_debug, legacy_debug)
                self.assertEqual(result["debug"], expected)

    def probe_email_settings(self, settings_module):
        environment = os.environ.copy()
        environment.update(
            DJANGO_SETTINGS_MODULE=settings_module,
            SECRET_KEY="test-only-secret-key",
            DATABASE_URL=(
                "postgresql://test:test@localhost:5432/test"
                if settings_module.endswith("production")
                else "sqlite:///:memory:"
            ),
            ALLOWED_HOSTS="testserver",
            DEFAULT_FROM_EMAIL="MotoService <no-reply@example.test>",
            BREVO_API_KEY="test-only-brevo-api-key",
            BREVO_FROM_EMAIL="brevo@example.test",
            BREVO_FROM_NAME="MotoService",
            PASSWORD_RESET_TIMEOUT="86400",
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import json
import django
django.setup()
from django.conf import settings
print(json.dumps({
    'backend': settings.EMAIL_BACKEND,
    'default_from_email': settings.DEFAULT_FROM_EMAIL,
    'brevo_from_email': settings.BREVO_FROM_EMAIL,
    'brevo_from_name': settings.BREVO_FROM_NAME,
    'has_brevo_api_key': bool(settings.BREVO_API_KEY),
    'reset_timeout': settings.PASSWORD_RESET_TIMEOUT,
}))
""",
            ],
            cwd=Path(settings.BASE_DIR),
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        return json.loads(result.stdout)

    def test_backends_email_por_entorno(self):
        desarrollo = self.probe_email_settings("config.settings.development")
        produccion = self.probe_email_settings("config.settings.production")

        self.assertEqual(
            desarrollo["backend"],
            "django.core.mail.backends.console.EmailBackend",
        )
        self.assertEqual(
            produccion["backend"],
            "apps.core.email_backends.BrevoEmailBackend",
        )
        self.assertTrue(produccion["has_brevo_api_key"])
        self.assertEqual(
            produccion["brevo_from_email"],
            "brevo@example.test",
        )
        self.assertEqual(produccion["brevo_from_name"], "MotoService")
        self.assertEqual(
            produccion["default_from_email"],
            "MotoService <no-reply@example.test>",
        )
        self.assertEqual(produccion["reset_timeout"], 86400)

    def test_produccion_exige_configuracion_brevo_explicita(self):
        for variable in (
            "BREVO_API_KEY",
            "BREVO_FROM_EMAIL",
            "BREVO_FROM_NAME",
        ):
            with self.subTest(variable=variable):
                environment = os.environ.copy()
                environment.update(
                    DJANGO_SETTINGS_MODULE="config.settings.production",
                    SECRET_KEY="test-only-secret-key",
                    DATABASE_URL="postgresql://test:test@localhost:5432/test",
                    ALLOWED_HOSTS="testserver",
                    BREVO_API_KEY="test-only-brevo-api-key",
                    BREVO_FROM_EMAIL="brevo@example.test",
                    BREVO_FROM_NAME="MotoService",
                )
                environment[variable] = ""
                result = subprocess.run(
                    [sys.executable, "-c", "import django; django.setup()"],
                    cwd=Path(settings.BASE_DIR),
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    f"{variable} must be set in production.",
                    result.stderr,
                )
                self.assertNotIn("test-only-brevo-api-key", result.stderr)

    def test_desarrollo_y_tests_no_exigen_configuracion_brevo(self):
        for settings_module, backend in (
            (
                "config.settings.development",
                "django.core.mail.backends.console.EmailBackend",
            ),
            (
                "config.settings.test",
                "django.core.mail.backends.locmem.EmailBackend",
            ),
        ):
            with self.subTest(settings_module=settings_module):
                environment = os.environ.copy()
                environment.update(
                    DJANGO_SETTINGS_MODULE=settings_module,
                    DATABASE_URL="sqlite:///:memory:",
                    BREVO_API_KEY="",
                    BREVO_FROM_EMAIL="",
                    BREVO_FROM_NAME="",
                )
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        (
                            "import django; django.setup(); "
                            "from django.conf import settings; "
                            "print(settings.EMAIL_BACKEND)"
                        ),
                    ],
                    cwd=Path(settings.BASE_DIR),
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=True,
                )
                self.assertEqual(result.stdout.strip(), backend)

    def test_env_example_documenta_email_y_limites_sin_credenciales(self):
        contenido = (Path(settings.BASE_DIR) / ".env.example").read_text(
            encoding="utf-8"
        )
        for nombre in (
            "DEFAULT_FROM_EMAIL",
            "BREVO_API_KEY",
            "BREVO_FROM_EMAIL",
            "BREVO_FROM_NAME",
            "PASSWORD_RESET_TIMEOUT",
            "AUTH_LOGIN_IP_MAX_ATTEMPTS",
            "AUTH_LOGIN_IDENTIFIER_MAX_ATTEMPTS",
            "AUTH_LOGIN_WINDOW_SECONDS",
            "PASSWORD_RESET_IP_MAX_ATTEMPTS",
            "PASSWORD_RESET_IDENTIFIER_MAX_ATTEMPTS",
            "PASSWORD_RESET_WINDOW_SECONDS",
            "TEST_DATABASE_URL",
        ):
            self.assertIn(f"{nombre}=", contenido)
        self.assertIn("BREVO_API_KEY=\n", contenido.replace("\r\n", "\n"))
        self.assertIn(
            "BREVO_FROM_EMAIL=servicemoto09@gmail.com",
            contenido,
        )
        self.assertIn("BREVO_FROM_NAME=MotoService", contenido)
        for nombre_smtp in (
            "EMAIL_HOST=",
            "EMAIL_PORT=",
            "EMAIL_HOST_USER=",
            "EMAIL_HOST_PASSWORD=",
            "EMAIL_USE_TLS=",
            "EMAIL_USE_SSL=",
        ):
            self.assertNotIn(nombre_smtp, contenido)


class ProductionDeploymentTests(SimpleTestCase):
    def test_render_yaml_es_la_unica_definicion_del_despliegue(self):
        base_dir = Path(settings.BASE_DIR)
        # Sin dependencias nuevas para parsear YAML: se verifican las líneas.
        blueprint = (base_dir / "render.yaml").read_text(encoding="utf-8")
        lineas = [linea.strip() for linea in blueprint.splitlines()]

        for esperada in (
            "- type: web",
            "runtime: python",
            "plan: free",
            "branch: main",
            "healthCheckPath: /healthz/",
            "value: config.settings.production",
        ):
            self.assertIn(esperada, lineas)
        self.assertEqual(reverse("core:healthz"), "/healthz/")
        self.assertRegex(blueprint, r"- key: PYTHON_VERSION\s+value: 3\.13\.\d+")
        self.assertRegex(blueprint, r"- key: WEB_CONCURRENCY\s+value: \"2\"")
        for secreto in (
            "SECRET_KEY",
            "DATABASE_URL",
            "BREVO_API_KEY",
            "BREVO_FROM_EMAIL",
            "BREVO_FROM_NAME",
            "ALLOWED_HOSTS",
            "CSRF_TRUSTED_ORIGINS",
        ):
            with self.subTest(variable=secreto):
                self.assertRegex(blueprint, rf"- key: {secreto}\s+sync: false")

        sin_comentarios = " ".join(
            linea for linea in lineas if linea and not linea.startswith("#")
        )
        build = sin_comentarios.split("buildCommand:", 1)[1].split("startCommand:", 1)[0]
        arranque = sin_comentarios.split("startCommand:", 1)[1].split(
            "healthCheckPath:", 1
        )[0]
        self.assertIn("pip install -r requirements.txt", build)
        self.assertIn("collectstatic --noinput --settings=config.settings.production", build)
        self.assertNotIn("migrate", build)
        # Sin pre-deploy en free: verificar la base, migrar y recién ahí Gunicorn.
        self.assertLess(arranque.index("verificar_base"), arranque.index("migrate --noinput"))
        self.assertLess(arranque.index("migrate --noinput"), arranque.index("exec gunicorn"))
        self.assertIn(
            "exec gunicorn -c gunicorn.conf.py config.wsgi:application", arranque
        )
        for archivo in ("Procfile", "railway.json"):
            self.assertFalse((base_dir / archivo).exists(), archivo)

    def entorno_produccion(self, database_url, **extra):
        environment = os.environ.copy()
        environment.update(
            DJANGO_SETTINGS_MODULE="config.settings.production",
            SECRET_KEY="test-only-secret-key",
            DATABASE_URL=database_url,
            ALLOWED_HOSTS="motoservice.example.test",
            BREVO_API_KEY="test-only-brevo-api-key",
            BREVO_FROM_EMAIL="brevo@example.test",
            BREVO_FROM_NAME="MotoService",
            RENDER_EXTERNAL_HOSTNAME="",
            AUTH_RATE_LIMIT_CLIENT_IP_HEADER="",
        )
        environment.update(extra)
        return environment

    def probe_production_settings(self, database_url, **extra):
        environment = self.entorno_produccion(database_url, **extra)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import json
import django
django.setup()
from django.conf import settings
print(json.dumps({
    'allowed_hosts': settings.ALLOWED_HOSTS,
    'redirect_exempt': settings.SECURE_REDIRECT_EXEMPT,
    'ssl_redirect': settings.SECURE_SSL_REDIRECT,
    'connect_timeout': settings.DATABASES['default']['OPTIONS']['connect_timeout'],
    'conn_max_age': settings.DATABASES['default']['CONN_MAX_AGE'],
    'conn_health_checks': settings.DATABASES['default']['CONN_HEALTH_CHECKS'],
    'client_ip_header': settings.AUTH_RATE_LIMIT_CLIENT_IP_HEADER,
}))
""",
            ],
            cwd=Path(settings.BASE_DIR),
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_produccion_exime_solo_healthz_del_redirect_https(self):
        produccion = self.probe_production_settings(
            "postgresql://test:test@localhost:5432/test"
        )
        exentas = produccion["redirect_exempt"]

        self.assertEqual(produccion["allowed_hosts"], ["motoservice.example.test"])
        self.assertTrue(produccion["ssl_redirect"])
        self.assertTrue(any(re.search(patron, "healthz/") for patron in exentas))
        self.assertFalse(any(re.search(patron, "clientes/") for patron in exentas))
        self.assertEqual(produccion["connect_timeout"], 10)

    def test_produccion_agrega_el_host_de_render_para_sus_health_checks(self):
        produccion = self.probe_production_settings(
            "postgresql://test:test@localhost:5432/test",
            RENDER_EXTERNAL_HOSTNAME="motoservice.onrender.com",
        )

        self.assertEqual(
            produccion["allowed_hosts"],
            ["motoservice.example.test", "motoservice.onrender.com"],
        )

    def test_produccion_usa_cf_connecting_ip_y_permite_configurarlo(self):
        por_defecto = self.probe_production_settings(
            "postgresql://test:test@localhost:5432/test"
        )
        configurado = self.probe_production_settings(
            "postgresql://test:test@localhost:5432/test",
            AUTH_RATE_LIMIT_CLIENT_IP_HEADER="X-Forwarded-For",
        )

        self.assertEqual(por_defecto["client_ip_header"], "CF-Connecting-IP")
        self.assertEqual(configurado["client_ip_header"], "X-Forwarded-For")

    def test_pooler_session_de_supabase_conserva_conexiones_verificadas(self):
        produccion = self.probe_production_settings(
            "postgresql://postgres.ref:clave@aws-0-sa-east-1.pooler.supabase.com:5432/postgres"
        )

        self.assertEqual(produccion["conn_max_age"], 600)
        self.assertTrue(produccion["conn_health_checks"])

    def test_produccion_rechaza_el_pooler_en_modo_transaction(self):
        result = subprocess.run(
            [sys.executable, "-c", "import django; django.setup()"],
            cwd=Path(settings.BASE_DIR),
            env=self.entorno_produccion(
                "postgresql://postgres.ref:clave-secreta@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
            ),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Session pooler (port 5432)", result.stderr)
        self.assertNotIn("clave-secreta", result.stderr)

    def test_connect_timeout_puede_ajustarse_desde_la_url(self):
        produccion = self.probe_production_settings(
            "postgresql://test:test@localhost:5432/test?connect_timeout=3"
        )

        self.assertEqual(int(produccion["connect_timeout"]), 3)


class GunicornConfigTests(SimpleTestCase):
    def cargar_config(self, **variables):
        """Ejecuta gunicorn.conf.py con un Logger mínimo: Gunicorn no corre en Windows."""

        class LoggerBase:
            def __init__(self):
                self.registradas = []

            def access(self, resp, req, environ, request_time):
                self.registradas.append(environ["PATH_INFO"])

            def atoms(self, resp, req, environ, request_time):
                return {"U": environ["PATH_INFO"], "q": environ.get("QUERY_STRING", "")}

        glogging = types.ModuleType("gunicorn.glogging")
        glogging.Logger = LoggerBase
        entorno = {
            clave: valor
            for clave, valor in os.environ.items()
            if not clave.startswith("GUNICORN_")
            and clave not in {"PORT", "LOG_LEVEL", "WEB_CONCURRENCY"}
        }
        entorno.update(variables)
        with (
            patch.dict(sys.modules, {"gunicorn.glogging": glogging}),
            patch.dict(os.environ, entorno, clear=True),
        ):
            return runpy.run_path(str(Path(settings.BASE_DIR) / "gunicorn.conf.py"))

    def test_valores_por_defecto(self):
        config = self.cargar_config()

        self.assertEqual(config["wsgi_app"], "config.wsgi:application")
        self.assertEqual(config["bind"], "0.0.0.0:10000")
        self.assertEqual(config["workers"], 2)
        self.assertEqual(config["timeout"], 60)
        self.assertEqual(config["graceful_timeout"], 30)
        self.assertEqual(config["accesslog"], "-")
        self.assertEqual(config["loglevel"], "info")

    def test_puerto_workers_y_timeouts_vienen_del_entorno(self):
        config = self.cargar_config(
            PORT="4321",
            WEB_CONCURRENCY="3",
            GUNICORN_TIMEOUT="90",
            GUNICORN_GRACEFUL_TIMEOUT="20",
            LOG_LEVEL="WARNING",
        )

        self.assertEqual(config["bind"], "0.0.0.0:4321")
        self.assertEqual(config["workers"], 3)
        self.assertEqual(config["timeout"], 90)
        self.assertEqual(config["graceful_timeout"], 20)
        self.assertEqual(config["loglevel"], "warning")

    def test_rechaza_workers_no_positivos(self):
        with self.assertRaises(ValueError):
            self.cargar_config(WEB_CONCURRENCY="0")

    def test_access_log_no_registra_query_ip_referer_ni_tokens(self):
        config = self.cargar_config()
        logger = config["logger_class"]()

        def ruta_registrada(path):
            return logger.atoms(None, None, {"PATH_INFO": path}, None)["U"]

        for atomo in ("%(q)s", "%(r)s", "%(h)s", "%(f)s", "%(a)s"):
            self.assertNotIn(atomo, config["access_log_format"])
        self.assertIn("%(U)s", config["access_log_format"])
        self.assertEqual(
            ruta_registrada("/accounts/reset/MQ/abc-123-token/"),
            "/accounts/reset/<oculto>/",
        )
        self.assertEqual(ruta_registrada("/clientes/"), "/clientes/")

    def test_healthchecks_exitosos_no_ensucian_el_access_log(self):
        logger = self.cargar_config()["logger_class"]()

        for ruta, estado in (
            ("/healthz/", 200),
            ("/healthz/", 503),
            ("/clientes/", 200),
        ):
            respuesta = types.SimpleNamespace(status_code=estado)
            logger.access(respuesta, None, {"PATH_INFO": ruta}, None)

        self.assertEqual(logger.registradas, ["/healthz/", "/clientes/"])

    @skipUnless(importlib.util.find_spec("fcntl"), "Gunicorn sólo corre en POSIX.")
    def test_gunicorn_real_acepta_la_configuracion(self):
        environment = os.environ.copy()
        environment["DJANGO_SETTINGS_MODULE"] = "config.settings.test"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "gunicorn",
                "--check-config",
                "--config",
                "gunicorn.conf.py",
            ],
            cwd=Path(settings.BASE_DIR),
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
