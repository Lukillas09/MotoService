# MotoService

[![Tests](https://github.com/Lukillas09/MotoService/actions/workflows/tests.yml/badge.svg)](https://github.com/Lukillas09/MotoService/actions/workflows/tests.yml)

Aplicación web para la gestión cotidiana de un taller de motos. Usa un monolito Django modular, responsive e instalable como PWA, con PostgreSQL como base oficial y Supabase PostgreSQL en producción.

Las fases 1 a 6 cubren el flujo operativo principal y su interfaz final:

```text
Cliente → Moto → Servicio → Mantenimiento → Alerta → Contacto
```

## Versión

Versión actual: **v1.0.2**.

`config/version.py` es la fuente de verdad de la versión de la aplicación. Los tags Git y releases deben coincidir con el valor definido en ese archivo, usando el prefijo `v`.

## Tecnologías

- Python y Django 5
- Django Templates, HTMX y Bootstrap 5
- PostgreSQL mediante `DATABASE_URL`
- WhiteNoise y Gunicorn
- Supabase PostgreSQL y Railway
- Brevo mediante su SDK oficial y API HTTPS para emails de producción
- `openpyxl` para la exportación Excel

## Funcionalidad actual

- autenticación con Django Auth, rate limiting persistente y vistas operativas privadas;
- roles simples Propietario/Usuario, invitaciones por email y recuperación de contraseña;
- perfil “Mi cuenta”, cambio de contraseña, desactivación y reactivación sin borrar historial;
- alta, edición, búsqueda y archivado/restauración de clientes y motos;
- búsqueda global por cliente, teléfono, patente, marca y modelo;
- servicios con fecha, estado, kilometraje, trabajos, precio y observaciones;
- historial completo por moto y conservación del propietario histórico;
- catálogo de mantenimientos con intervalos configurables por meses y kilómetros;
- cálculo centralizado de próximos mantenimientos y vencimientos;
- dashboard y cola de alertas con filtros y actualización mediante HTMX;
- seguimiento por ciclo y propietario, con historial de eventos;
- contacto manual por WhatsApp mediante enlaces `wa.me` con mensaje precargado;
- acciones de contacto, posposición, turno, no interesado, notas y reapertura;
- exportaciones CSV de clientes, motos, servicios, mantenimientos y seguimientos, reservadas a Propietarios;
- Excel completo con todos los datos operativos;
- backup manual recuperable del schema PostgreSQL mediante `pg_dump`;
- interfaz final responsive con sidebar y topbar en escritorio;
- navegación inferior y menú contextual en móvil;
- representación visual genérica de motos sin fotos ni almacenamiento multimedia;
- PWA instalable con iconos PNG, icono maskable y caché exclusiva de recursos estáticos;
- guía de uso integrada, privada y responsive, con búsqueda local, tutoriales y preguntas frecuentes.

La patente se guarda en mayúsculas y sin espacios ni guiones. El kilometraje de la moto representa el último valor conocido por el taller, nunca una lectura automática.

### Estado técnico y seguimiento humano

El estado técnico de un mantenimiento se deriva al consultar la aplicación a partir del último servicio válido, la fecha, el kilometraje registrado y la regla configurable. Puede ser `AL_DIA`, `PROXIMO`, `VENCIDO`, `SIN_REGISTRO`, `DATOS_INSUFICIENTES` o `NO_CONFIGURADO`; las alertas no se guardan en la base.

El seguimiento humano sí se persiste y puede estar `PENDIENTE`, `CONTACTADO`, `POSPUESTO`, `TURNO_ACORDADO` o `NO_INTERESADO`. Contactar o posponer a un cliente no modifica el vencimiento técnico. Cada acción queda asociada al ciclo de mantenimiento y al propietario correspondiente.

## Requisitos

- Python 3.12 o una versión compatible con Django 5
- PostgreSQL para desarrollo real o Supabase PostgreSQL en producción

Si `DATABASE_URL` está vacío, la configuración de desarrollo usa SQLite como comodidad local. Los tests usan SQLite en memoria por defecto y nunca toman `DATABASE_URL`. Para probar locks reales puede definirse exclusivamente `TEST_DATABASE_URL` contra una instancia PostgreSQL descartable con permiso para crear la base de test; nunca debe apuntar a producción ni a Supabase productivo.

## Instalación local

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Rutas principales:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/clientes/`
- `http://127.0.0.1:8000/motos/`
- `http://127.0.0.1:8000/servicios/`
- `http://127.0.0.1:8000/mantenimientos/`
- `http://127.0.0.1:8000/mantenimientos/configuracion/`
- `http://127.0.0.1:8000/exportaciones/` (solo Propietario)
- `http://127.0.0.1:8000/guia/`
- `http://127.0.0.1:8000/cuenta/`
- `http://127.0.0.1:8000/usuarios/` (solo Propietario)
- `http://127.0.0.1:8000/admin/`
- `http://127.0.0.1:8000/healthz/` (público, sin datos)

Las vistas operativas requieren iniciar sesión en `/accounts/login/`. El repositorio no incluye credenciales predeterminadas.

No existe registro público. Un Propietario crea cada cuenta desde `/usuarios/`; la persona recibe un enlace de 24 horas para elegir su propia contraseña. Los superusuarios existentes se reconocen como Propietarios sin modificar sus flags. El rol Propietario también puede asignarse mediante el Group de Django `Propietario`; `is_staff` conserva su significado administrativo de Django y no representa el rol del taller.

## Interfaz y PWA

La interfaz prioriza alertas accionables, búsqueda y registro rápido de servicios. En escritorio utiliza una navegación lateral estable y una barra superior; por debajo de 992 px utiliza una cabecera compacta, navegación inferior y un offcanvas “Más”. Los listados se convierten en cards cuando el ancho no permite conservar una fila legible.

Las motos se representan con `static/images/moto-generic.png`, un asset optimizado propio de MotoService. La identidad usa un brand mark local y variantes específicas para interfaz, favicon y PWA. No existe un campo de foto, carga de archivos ni dependencia de imágenes externas. El criterio visual y los estados reutilizables están documentados en [docs/ui-ux.md](docs/ui-ux.md).

La guía de uso vive dentro de la aplicación, requiere iniciar sesión y se mantiene junto con el código, sin modelos ni CMS. Incluye tutoriales del flujo operativo, ayuda contextual y capturas generadas sobre una base local aislada con datos ficticios. El inventario de capturas está en [docs/guia.md](docs/guia.md).

El service worker sólo intercepta solicitudes `GET` del mismo origen bajo `/static/`. No almacena dashboard, clientes, motos, exportaciones ni ninguna otra respuesta privada. La aplicación requiere conexión para acceder a los datos del taller.

## Variables de entorno

Copiar `.env.example` como `.env` y completar:

```env
DJANGO_DEBUG=True
SECRET_KEY=change-me
DATABASE_URL=
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=
DJANGO_SETTINGS_MODULE=config.settings.development
WHATSAPP_DEFAULT_COUNTRY_CODE=549
TALLER_NOMBRE=
DEFAULT_FROM_EMAIL=
BREVO_API_KEY=
BREVO_FROM_EMAIL=servicemoto09@gmail.com
BREVO_FROM_NAME=MotoService
PASSWORD_RESET_TIMEOUT=86400
AUTH_LOGIN_IP_MAX_ATTEMPTS=20
AUTH_LOGIN_IDENTIFIER_MAX_ATTEMPTS=10
AUTH_LOGIN_WINDOW_SECONDS=900
PASSWORD_RESET_IP_MAX_ATTEMPTS=10
PASSWORD_RESET_IDENTIFIER_MAX_ATTEMPTS=5
PASSWORD_RESET_WINDOW_SECONDS=3600
TEST_DATABASE_URL=
LISTADO_POR_PAGINA=25
LOG_LEVEL=INFO
```

`WHATSAPP_DEFAULT_COUNTRY_CODE` se usa para normalizar teléfonos sin prefijo internacional y `TALLER_NOMBRE` personaliza el mensaje precargado. En producción, `SECRET_KEY` y `DATABASE_URL` son obligatorias; `SECRET_KEY=change-me` se rechaza.

`LISTADO_POR_PAGINA` define cuántos registros muestran por página los listados de clientes, motos, servicios y alertas (entero positivo, 25 por defecto).

`LOG_LEVEL` controla el nivel de los loggers `django` y `apps` (`DEBUG`, `INFO`, `WARNING`, `ERROR` o `CRITICAL`; `INFO` por defecto y `WARNING` en tests). Los registros salen por stdout con fecha, nivel, logger y mensaje, así quedan en los logs de Railway. `django.request` y `django.security` nunca bajan de `WARNING`, por lo que los errores 500 quedan registrados aunque no haya `ADMINS`. Los logs no incluyen cuerpos de email, tokens, contraseñas, destinatarios ni secretos.

Los seis valores `*_MAX_ATTEMPTS` y `*_WINDOW_SECONDS` controlan las ventanas del login normal, el login del admin y la recuperación. Deben ser enteros positivos. Los contadores se guardan en PostgreSQL con sujetos HMAC, vencen por ventana y pueden purgarse sin un worker mediante `python manage.py limpiar_limites_autenticacion`.

En desarrollo, `DJANGO_DEBUG` controla el modo de depuración y la entrega de estáticos de `runserver`. Tiene prioridad sobre la variable anterior `DEBUG`, que sigue siendo compatible con valores booleanos. Valores ajenos a Django, como `DEBUG=release` heredado del entorno, utilizan el valor predeterminado de desarrollo (`True`). Producción siempre fuerza `DEBUG=False`.

El desarrollo usa `ConsoleEmailBackend`: al crear una cuenta o solicitar recuperación, el email y su enlace aparecen en la terminal de `runserver` sin contactar un proveedor. Los tests usan `locmem.EmailBackend` y nunca hacen requests reales. Producción conserva la API de email de Django y entrega mediante `BrevoEmailBackend`, el SDK oficial `brevo-python` y la API HTTPS de Brevo. No se usa SMTP.

`BREVO_FROM_EMAIL` y `BREVO_FROM_NAME` son la fuente de verdad del remitente en producción; no están hardcodeados en el backend. La configuración prevista usa el remitente verificado `MotoService <servicemoto09@gmail.com>`. `BREVO_API_KEY` es un secreto y debe existir sólo en el entorno de ejecución. `DEFAULT_FROM_EMAIL` se mantiene por compatibilidad con la API de Django y los entornos locales.

El backend requiere al menos un destinatario principal en `to`, porque la operación usada de Brevo no representa un envío dirigido sólo a `cc`/`bcc`. Brevo admite un único `reply-to`, por lo que el backend rechaza explícitamente mensajes Django con más de uno. Los adjuntos todavía no se usan en MotoService y también se rechazan de forma explícita; nunca se descarta silenciosamente información del mensaje.

Para probar localmente con SQLite, dejá `DATABASE_URL` vacío y ejecutá:

```powershell
.\.venv\Scripts\python.exe manage.py runserver 8001
```

Abrí el enlace de invitación o recuperación que Django imprime en esa misma terminal. Usá únicamente cuentas y correos ficticios durante las pruebas.

## Verificaciones

```powershell
.\.venv\Scripts\python.exe manage.py check --settings=config.settings.test
.\.venv\Scripts\python.exe manage.py test --settings=config.settings.test
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=config.settings.test
```

Las pruebas marcadas como PostgreSQL se omiten honestamente con SQLite. Para ejecutarlas, definí `TEST_DATABASE_URL` con credenciales de una instancia local y descartable; Django creará su base de test. La suite rechaza una URL que no sea PostgreSQL.

### Integración continua

`.github/workflows/tests.yml` corre en cada push y pull request con Python 3.13 y un service `postgres:17` propio del job. Define `TEST_DATABASE_URL` hacia ese service, de modo que los tests de concurrencia e índice de email normalizado se ejecutan en vez de omitirse; un paso previo falla si la conexión no es PostgreSQL. El job ejecuta `makemigrations --check --dry-run`, `check`, `check --deploy` con settings de producción y valores ficticios, y la suite completa. La única advertencia esperada de `check --deploy` es `security.W004` (HSTS), que se habilitará al confirmar el dominio definitivo.

## Estructura

```text
.github/workflows/      CI de tests sobre PostgreSQL y keepalive de /healthz/
config/                 Configuración Django y settings por entorno
apps/                   Apps internas del proyecto
templates/              Templates globales
static/                 CSS, JavaScript, manifest, service worker e iconos PWA
docs/                   Documentación de producto y arquitectura
```

## Railway

`railway.json` es la única fuente de verdad del despliegue (no hay `Procfile`):

- **build**: `collectstatic` con settings de producción, así los estáticos quedan dentro de la imagen. Railway expone las variables del servicio durante el build, por eso `SECRET_KEY`, `DATABASE_URL` y las de Brevo ya deben existir.
- **preDeployCommand**: `migrate`. Si la base no responde, el deploy nuevo se cancela y la versión anterior sigue atendiendo.
- **startCommand**: sólo `gunicorn --config gunicorn.conf.py`. Arrancar no requiere base de datos, por lo que una base pausada ya no produce un loop de reinicios.
- **healthcheckPath** `/healthz/` con `healthcheckTimeout` de 120 s: Railway sólo pasa el tráfico al deploy nuevo cuando responde 200.

`/healthz/` es público, no usa sesión, CSRF ni rate limiting, responde `Cache-Control: no-store` y devuelve únicamente `{"status": "ok", "database": "ok"}` (200) o `{"status": "error", "database": "unavailable"}` (503) según un `SELECT 1`. La conexión a PostgreSQL usa `connect_timeout=10`, ajustable con `?connect_timeout=` en `DATABASE_URL`.

`gunicorn.conf.py` escucha en `0.0.0.0:$PORT` y toma `GUNICORN_WORKERS` (2), `GUNICORN_TIMEOUT` (60 s) y `GUNICORN_GRACEFUL_TIMEOUT` (30 s) del entorno. El access log sale por stdout sin IP, referer, user agent ni query string, y oculta el token de los enlaces de invitación y recuperación.

En Railway se deben configurar:

- `DJANGO_SETTINGS_MODULE=config.settings.production`
- `SECRET_KEY`
- `DATABASE_URL`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `WHATSAPP_DEFAULT_COUNTRY_CODE`
- `TALLER_NOMBRE`
- `BREVO_API_KEY`
- `BREVO_FROM_EMAIL=servicemoto09@gmail.com`
- `BREVO_FROM_NAME=MotoService`
- `PASSWORD_RESET_TIMEOUT`
- `AUTH_LOGIN_IP_MAX_ATTEMPTS`
- `AUTH_LOGIN_IDENTIFIER_MAX_ATTEMPTS`
- `AUTH_LOGIN_WINDOW_SECONDS`
- `PASSWORD_RESET_IP_MAX_ATTEMPTS`
- `PASSWORD_RESET_IDENTIFIER_MAX_ATTEMPTS`
- `PASSWORD_RESET_WINDOW_SECONDS`
- opcionales: `LOG_LEVEL`, `LISTADO_POR_PAGINA`, `GUNICORN_WORKERS`, `GUNICORN_TIMEOUT`, `GUNICORN_GRACEFUL_TIMEOUT`

La configuración de producción fuerza `DEBUG=False`, exige PostgreSQL con SSL, confía en el proxy HTTPS de Railway, redirige a HTTPS y usa cookies seguras. El healthcheck interno de Railway llega por HTTP con el host `healthcheck.railway.app`: ese host se agrega a `ALLOWED_HOSTS` y `/healthz/` está en `SECURE_REDIRECT_EXEMPT`; el resto del sitio sigue redirigiendo a HTTPS.

Para que Supabase no pause la base por inactividad, `.github/workflows/keepalive.yml` consulta `/healthz/` cada 3 días. Requiere la variable de repositorio `HEALTHCHECK_URL` (por ejemplo `https://<dominio>/healthz/`); sin ella el job termina sin fallar. Los detalles están en [docs/architecture.md](docs/architecture.md).

Railway no necesita `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` ni `EMAIL_USE_SSL`: MotoService usa la API HTTPS de Brevo y no SMTP en producción. `BREVO_API_KEY` se configura únicamente como variable del servicio y nunca debe copiarse al repositorio, logs ni templates. Los enlaces de email se construyen desde el request y respetan el proxy HTTPS; no contienen un dominio hardcodeado.

Después del deploy, una prueba manual controlada puede ejecutarse desde una shell de Railway, reemplazando únicamente el destinatario de ejemplo:

```text
python manage.py shell -c "from django.core.mail import send_mail; print(send_mail('Prueba MotoService', 'Entrega de prueba mediante Brevo HTTPS.', None, ['destinatario@example.com'], fail_silently=False))"
```

El comando usa las variables ya configuradas en Railway; no hay que escribir ni mostrar la API key.

## Exportaciones y backups

La pantalla `/exportaciones/`, sus siete CSV, el Excel completo y las instrucciones de backup requieren rol Propietario o superuser. Un Usuario autenticado recibe HTTP 403 aunque intente abrir la URL directamente. Son archivos legibles para análisis y portabilidad; no reemplazan una copia recuperable de PostgreSQL.

El backup real se crea manualmente desde una computadora controlada con las herramientas cliente de PostgreSQL:

```text
python manage.py backup_database --output-dir "/ruta/privada/MotoService"
```

No se ejecuta desde el navegador ni se guarda permanentemente en Railway. El procedimiento de validación, custodia y restauración segura está en [docs/backups.md](docs/backups.md).

## Licencia

MotoService es software propietario. Todos los derechos reservados.

Consultá el archivo LICENSE para conocer las condiciones de uso.
