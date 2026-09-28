# gestor-taller-motos

Aplicación web para la gestión cotidiana de un taller de motos. Usa un monolito Django modular, responsive e instalable como PWA, con PostgreSQL como base oficial y Supabase PostgreSQL en producción.

Las fases 1 a 6 cubren el flujo operativo principal y su interfaz final:

```text
Cliente → Moto → Servicio → Mantenimiento → Alerta → Contacto
```

## Tecnologías

- Python y Django 5
- Django Templates, HTMX y Bootstrap 5
- PostgreSQL mediante `DATABASE_URL`
- WhiteNoise y Gunicorn
- Supabase PostgreSQL y Railway
- `openpyxl` para la exportación Excel

## Funcionalidad actual

- autenticación con Django Auth, gestión privada de usuarios y vistas operativas privadas;
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
- exportaciones CSV de clientes, motos, servicios, mantenimientos y seguimientos;
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

Si `DATABASE_URL` está vacío, la configuración de desarrollo usa SQLite como comodidad local. La configuración de tests siempre usa SQLite en memoria y no consulta Supabase.

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
- `http://127.0.0.1:8000/exportaciones/`
- `http://127.0.0.1:8000/guia/`
- `http://127.0.0.1:8000/cuenta/`
- `http://127.0.0.1:8000/usuarios/` (solo Propietario)
- `http://127.0.0.1:8000/admin/`

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
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=
EMAIL_TIMEOUT=10
PASSWORD_RESET_TIMEOUT=86400
```

`WHATSAPP_DEFAULT_COUNTRY_CODE` se usa para normalizar teléfonos sin prefijo internacional y `TALLER_NOMBRE` personaliza el mensaje precargado. En producción, `SECRET_KEY` y `DATABASE_URL` son obligatorias; `SECRET_KEY=change-me` se rechaza.

En desarrollo, `DJANGO_DEBUG` controla el modo de depuración y la entrega de estáticos de `runserver`. Tiene prioridad sobre la variable anterior `DEBUG`, que sigue siendo compatible con valores booleanos. Valores ajenos a Django, como `DEBUG=release` heredado del entorno, utilizan el valor predeterminado de desarrollo (`True`). Producción siempre fuerza `DEBUG=False`.

El desarrollo usa `ConsoleEmailBackend`: al crear una cuenta o solicitar recuperación, el email y su enlace aparecen en la terminal de `runserver` sin contactar un proveedor. Los tests usan el backend en memoria. Producción usa SMTP y requiere configurar sus variables en Railway antes de utilizar invitaciones o recuperación reales. `EMAIL_USE_TLS` y `EMAIL_USE_SSL` no pueden activarse simultáneamente.

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

## Estructura

```text
config/                 Configuración Django y settings por entorno
apps/                   Apps internas del proyecto
templates/              Templates globales
static/                 CSS, JavaScript, manifest, service worker e iconos PWA
docs/                   Documentación de producto y arquitectura
```

## Railway

El proyecto incluye `Procfile` y `railway.json`. En Railway se deben configurar:

- `DJANGO_SETTINGS_MODULE=config.settings.production`
- `SECRET_KEY`
- `DATABASE_URL`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `WHATSAPP_DEFAULT_COUNTRY_CODE`
- `TALLER_NOMBRE`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `EMAIL_USE_SSL`
- `DEFAULT_FROM_EMAIL`
- `EMAIL_TIMEOUT`
- `PASSWORD_RESET_TIMEOUT`

La configuración de producción fuerza `DEBUG=False`, exige PostgreSQL con SSL, confía en el proxy HTTPS de Railway, redirige a HTTPS y usa cookies seguras. El comando de inicio ejecuta migraciones, `collectstatic` y luego Gunicorn.

Las credenciales SMTP se configuran únicamente como variables del servicio. Nunca deben copiarse al repositorio, README, logs ni templates. Los enlaces de email se construyen desde el request y respetan el proxy HTTPS; no contienen un dominio hardcodeado.

## Exportaciones y backups

La pantalla `/exportaciones/` permite descargar siete CSV y un Excel completo. Son archivos legibles para análisis y portabilidad; no reemplazan una copia recuperable de PostgreSQL.

El backup real se crea manualmente desde una computadora controlada con las herramientas cliente de PostgreSQL:

```text
python manage.py backup_database --output-dir "/ruta/privada/MotoService"
```

No se ejecuta desde el navegador ni se guarda permanentemente en Railway. El procedimiento de validación, custodia y restauración segura está en [docs/backups.md](docs/backups.md).
