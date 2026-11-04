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
- Supabase PostgreSQL (pooler en modo Session) y Render
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

`LOG_LEVEL` controla el nivel de los loggers `django` y `apps` (`DEBUG`, `INFO`, `WARNING`, `ERROR` o `CRITICAL`; `INFO` por defecto y `WARNING` en tests). Los registros salen por stdout con fecha, nivel, logger y mensaje, así quedan en los logs de Render. `django.request` y `django.security` nunca bajan de `WARNING`, por lo que los errores 500 quedan registrados aunque no haya `ADMINS`. Los logs no incluyen cuerpos de email, tokens, contraseñas, destinatarios ni secretos.

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
.github/workflows/      CI de tests sobre PostgreSQL
render.yaml             Blueprint de Render (única definición del despliegue)
gunicorn.conf.py        Configuración de Gunicorn
config/                 Configuración Django y settings por entorno
apps/                   Apps internas del proyecto
templates/              Templates globales
static/                 CSS, JavaScript, manifest, service worker e iconos PWA
docs/                   Documentación de producto y arquitectura
```

## Render

`render.yaml` (Blueprint) es la única definición del despliegue; no hay `Procfile` ni `railway.json`. Define un web service Python en plan free sobre la rama `main`:

- **buildCommand**: instala `requirements.txt` y corre `collectstatic` con settings de producción, así los estáticos quedan en el build. Render expone las variables del servicio durante el build, por eso `SECRET_KEY`, `DATABASE_URL` y las de Brevo ya deben existir.
- **startCommand**: `verificar_base`, `migrate --noinput` y `exec gunicorn -c gunicorn.conf.py config.wsgi:application`. El plan free no tiene pre-deploy, así que las migraciones corren en cada arranque (también al despertar). `verificar_base` hace `SELECT 1` y, si la base no responde, corta en segundos con un mensaje que indica revisar Supabase y el pooler, sin mostrar la URL.
- **healthCheckPath** `/healthz/`: Render no pasa tráfico a un deploy nuevo hasta que responde 2xx y, con el servicio activo, lo consulta cada pocos segundos; tras 60 s de fallas reinicia la instancia.
- **autoDeployTrigger** `checksPass`: cada commit en `main` se despliega cuando el CI de GitHub Actions pasa.
- `PYTHON_VERSION` fija Python 3.13 (Render exige la versión completa) y `WEB_CONCURRENCY=2` sobrescribe el valor que Render calcula para 512 MB.

`/healthz/` es público, no usa sesión, CSRF ni rate limiting, está exento de `SECURE_SSL_REDIRECT` mediante `SECURE_REDIRECT_EXEMPT` y responde `Cache-Control: no-store` con únicamente `{"status": "ok", "database": "ok"}` (200) o `{"status": "error", "database": "unavailable"}` (503) según un `SELECT 1`. Los health checks exitosos no se escriben en el access log. La conexión usa `connect_timeout=10`, ajustable con `?connect_timeout=` en `DATABASE_URL`.

`gunicorn.conf.py` escucha en `0.0.0.0:$PORT` (10000 si falta) y toma `WEB_CONCURRENCY` (2), `GUNICORN_TIMEOUT` (60 s) y `GUNICORN_GRACEFUL_TIMEOUT` (30 s) del entorno. El access log sale por stdout sin IP, referer, user agent ni query string, y oculta el token de los enlaces de invitación y recuperación.

La configuración de producción fuerza `DEBUG=False`, exige PostgreSQL con SSL, confía en `X-Forwarded-Proto` del proxy de Render, redirige a HTTPS y usa cookies seguras. Además agrega `RENDER_EXTERNAL_HOSTNAME`, que Render define y usa como Host de sus health checks, a `ALLOWED_HOSTS`.

El rate limiting toma la IP del header indicado en `AUTH_RATE_LIMIT_CLIENT_IP_HEADER` (en producción, `CF-Connecting-IP` por defecto), valida su formato y usa `REMOTE_ADDR` si falta o es inválido. Render pone Cloudflare delante de los web services: Cloudflare sobrescribe `CF-Connecting-IP`, mientras que `X-Forwarded-For` conserva lo que mande el cliente. Si se configura `X-Forwarded-For`, se usa sólo la última entrada (la del proxy), nunca la primera.

Render free no tiene shell. Para probar el envío de email después del deploy, generá una invitación o una recuperación de contraseña hacia una cuenta propia. Producción no necesita `EMAIL_HOST` ni el resto de variables SMTP, que además están bloqueadas en el plan free: MotoService usa la API HTTPS de Brevo. `BREVO_API_KEY` se configura únicamente como variable del servicio y nunca debe copiarse al repositorio, logs ni templates.

## Hosting gratuito

MotoService corre sin costo en **Render free** (aplicación) y **Supabase free** (PostgreSQL).

### Base de datos: pooler de Supabase en modo Session

`DATABASE_URL` debe ser la cadena del **Session pooler** de Supabase (Connect → Connection string → Session pooler):

```text
postgresql://postgres.<project-ref>:<contraseña>@aws-0-<región>.pooler.supabase.com:5432/postgres
```

- El host directo `db.<project-ref>.supabase.co` del plan free es sólo IPv6 y Render sale por IPv4: no conecta.
- No uses el **Transaction pooler** (puerto 6543): no conserva la sesión entre sentencias y rompe `LOCK TABLE` y `select_for_update`, de los que dependen las migraciones, el rate limiting y la concurrencia. Producción se niega a arrancar si detecta `*.pooler.supabase.com:6543`.
- En modo Session cada conexión de Django ocupa una conexión real del pooler. Con 2 workers y `CONN_MAX_AGE=600` se mantienen como máximo 2 conexiones persistentes, muy por debajo del límite del plan free. `CONN_HEALTH_CHECKS` verifica cada conexión antes de reutilizarla, lo que cubre cierres por inactividad del pooler o el reposo de Render.

### Crear el servicio desde el Blueprint

1. Creá el proyecto en Supabase y copiá la cadena del Session pooler.
2. Si querés, ajustá `region` en `render.yaml` a la región de Render más cercana a Supabase; no se puede cambiar después.
3. En Render: **New → Blueprint**, conectá el repositorio de GitHub y elegí la rama `main`. Render detecta `render.yaml`.
4. Render pide los valores marcados con `sync: false`. Ejemplos:

   ```env
   SECRET_KEY=<cadena aleatoria larga: python -c "import secrets; print(secrets.token_urlsafe(50))">
   DATABASE_URL=postgresql://postgres.<project-ref>:<contraseña>@aws-0-<región>.pooler.supabase.com:5432/postgres
   ALLOWED_HOSTS=<app>.onrender.com
   CSRF_TRUSTED_ORIGINS=https://<app>.onrender.com
   BREVO_API_KEY=<clave de Brevo>
   BREVO_FROM_EMAIL=servicemoto09@gmail.com
   BREVO_FROM_NAME=MotoService
   ```

   Opcionales, desde Environment en el dashboard: `TALLER_NOMBRE`, `WHATSAPP_DEFAULT_COUNTRY_CODE`, `LOG_LEVEL`, `LISTADO_POR_PAGINA`, `AUTH_RATE_LIMIT_CLIENT_IP_HEADER`, `GUNICORN_TIMEOUT`, `GUNICORN_GRACEFUL_TIMEOUT`, `PASSWORD_RESET_TIMEOUT` y los límites `AUTH_LOGIN_*` / `PASSWORD_RESET_*`.
5. **Apply**. El primer deploy construye, migra y arranca. Verificá `https://<app>.onrender.com/healthz/`: tiene que responder `{"status": "ok", "database": "ok"}`.
6. Creá el primer Propietario desde tu PC, porque Render free no tiene shell: con `DATABASE_URL` del Session pooler definida sólo en esa terminal (nunca en un archivo versionado), corré `python manage.py createsuperuser`.

### Ping cada 10 minutos (cron-job.org)

Render free duerme el servicio tras 15 minutos sin tráfico y Supabase free pausa los proyectos inactivos. Un ping externo evita ambas cosas sin infraestructura propia:

1. Creá una cuenta en [cron-job.org](https://cron-job.org) y un cronjob nuevo.
2. URL: `https://<app>.onrender.com/healthz/`, método GET.
3. Programación: cada 10 minutos.
4. Activá las notificaciones por falla: un 503 indica que la base no responde.

Cada ping ejecuta un `SELECT 1`, no crea sesión ni consume el rate limiting y no se escribe en el access log si responde 200.

### Backups

Render free no tiene shell ni discos persistentes, así que el backup con `pg_dump` se corre **desde tu PC** contra Supabase, con las herramientas cliente de PostgreSQL (versión mayor igual o más nueva que la del servidor) y `DATABASE_URL` apuntando al Session pooler sólo en esa terminal:

```text
python manage.py backup_database --output-dir "/ruta/privada/MotoService"
```

El procedimiento completo está en [docs/backups.md](docs/backups.md).

### Limitaciones del plan free

- Si el ping falla o se desactiva, el servicio se duerme y el primer acceso tarda alrededor de un minuto, más el tiempo de `migrate` al arrancar.
- Render da 750 horas de instancia free por mes y por workspace. Un servicio despierto todo el mes usa unas 744 h, así que no conviene tener otro servicio free activo en el mismo workspace.
- Render puede reiniciar las instancias free en cualquier momento. Cada arranque vuelve a verificar la base y migrar; si la base no responde, el arranque falla hasta que vuelva.
- Sin discos persistentes: nada del negocio se guarda en el filesystem del servicio.
- Puertos SMTP bloqueados: no afecta, el email sale por la API HTTPS de Brevo.

## Exportaciones y backups

La pantalla `/exportaciones/`, sus siete CSV, el Excel completo y las instrucciones de backup requieren rol Propietario o superuser. Un Usuario autenticado recibe HTTP 403 aunque intente abrir la URL directamente. Son archivos legibles para análisis y portabilidad; no reemplazan una copia recuperable de PostgreSQL.

El backup real se crea manualmente desde una computadora controlada con las herramientas cliente de PostgreSQL:

```text
python manage.py backup_database --output-dir "/ruta/privada/MotoService"
```

No se ejecuta desde el navegador ni en Render: se corre desde una PC controlada (ver Hosting gratuito). El procedimiento de validación, custodia y restauración segura está en [docs/backups.md](docs/backups.md).

## Licencia

MotoService es software propietario. Todos los derechos reservados.

Consultá el archivo LICENSE para conocer las condiciones de uso.
