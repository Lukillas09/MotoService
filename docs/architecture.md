# Arquitectura

El proyecto usa un monolito Django modular:

```text
Django monolitico modular -> Railway -> Supabase PostgreSQL
```

Django concentra templates, autenticacion, reglas de negocio, vistas y admin en una sola aplicacion web. Las apps dentro de `apps/` separan responsabilidades sin convertir el sistema en microservicios.

La app `servicios` administra las visitas al taller y conserva una referencia histórica al cliente que era propietario al momento del registro. La app `mantenimientos` administra el catálogo, las reglas configurables, los trabajos realizados y el cálculo de próximos mantenimientos.

El alta y la edición de un servicio se ejecutan dentro de una transacción. La misma operación guarda el servicio, sincroniza sus mantenimientos y actualiza el último kilometraje conocido de la moto solo si el nuevo valor es mayor. El alta bloquea explícitamente Cliente y luego Moto; vuelve a comprobar que ambos sigan activos y conserva ese Cliente como referencia histórica. Antes de quitar un mantenimiento realizado, el servicio verifica si existe seguimiento de contacto y rechaza la edición con un error de dominio para conservar el ciclo y su historial.

La edición normal de una moto no admite reducir ni vaciar su último kilometraje conocido. Además del formulario, `Moto.save()` bloquea la fila existente cuando el guardado incluye kilometraje y rechaza instancias obsoletas que intenten sobrescribir un valor mayor. Los `update_fields` que no incluyen ese campo no lo modifican.

Railway sera el hosting de la aplicacion Django. Supabase se usara principalmente como PostgreSQL administrado en produccion.

## Producción

La configuración de producción exige `SECRET_KEY` y `DATABASE_URL`, mantiene `DEBUG=False`, requiere PostgreSQL con SSL y toma hosts y orígenes CSRF desde variables de entorno. Django confía en el encabezado HTTPS del proxy de Railway, redirige a HTTPS y marca como seguras las cookies de sesión y CSRF. El rate limiting toma la IP remota del encabezado `X-Real-IP` provisto por Railway, valida su formato y usa `REMOTE_ADDR` como fallback; nunca confía en `X-Forwarded-For` arbitrario.

WhiteNoise sirve los estáticos generados por `collectstatic` con el backend comprimido y con manifiesto configurado mediante `STORAGES`. El service worker se publica desde la raíz requerida por su alcance, pero sólo intercepta solicitudes GET bajo `/static/`. Un middleware central marca el HTML autenticado como `private, no-store` sin modificar estáticos, manifest, service worker, login público ni descargas con política propia. HSTS se habilitará al cerrar el despliegue, después de confirmar el dominio y HTTPS de extremo a extremo.

La versión oficial de la aplicación se define explícitamente en `config/version.py` y llega a los templates mediante un context processor de `core`. No depende de Git ni del filesystem del contenedor, y los tags publicados deben coincidir con esa fuente de verdad.

La arquitectura evita Redis, Celery, servicios adicionales y frontend separado mientras no exista una necesidad concreta. Esto reduce costos, complejidad operativa y mantenimiento.

Las vistas privadas usan Django Auth. Los listados y filtros conservan un fallback HTTP normal y HTMX se limita a reemplazar resultados o mostrar el contexto de la moto seleccionada. Clientes, motos, servicios y alertas se paginan con `Paginator.get_page` (`LISTADO_POR_PAGINA`, 25 por defecto); cada QuerySet tiene orden explícito con desempate por PK y las alertas, calculadas en memoria, se paginan después de filtrar y ordenar sin alterar los conteos del encabezado ni del dashboard. HTMX no conserva historial en `localStorage`: volver atrás recarga la página completa desde el servidor.

### Arranque en Railway

`railway.json` es la única definición del despliegue. `collectstatic` corre en el build, porque el pre-deploy se ejecuta en un contenedor aparte cuyo filesystem no llega al servicio; `migrate` corre como `preDeployCommand`, y `startCommand` sólo inicia Gunicorn con `gunicorn.conf.py`. Así, una base caída o un Supabase pausado no impiden arrancar ni generan un loop de reinicios: un deploy nuevo falla en el pre-deploy o en el healthcheck y Railway mantiene la versión anterior; un servicio ya activo sigue en pie y responde 503 en `/healthz/` hasta que la base vuelve.

`/healthz/` es una vista de `core` pública, `GET`/`HEAD`, exenta de CSRF y fuera del rate limiting, que ejecuta `SELECT 1` y devuelve 200 o 503 con `Cache-Control: no-store` y sin datos del taller. El middleware de caché privada revisa el tipo de respuesta antes que el usuario, de modo que respuestas que no son HTML no cargan la sesión. El healthcheck interno de Railway entra por HTTP con host `healthcheck.railway.app`: producción agrega ese host a `ALLOWED_HOSTS` (el edge público no enruta ese host al servicio) y exime sólo `^healthz/$` de `SECURE_SSL_REDIRECT`. La conexión usa `connect_timeout=10` para que una base inaccesible responda 503 rápido en lugar de agotar el timeout del worker.

Gunicorn escucha en `0.0.0.0:$PORT` con workers, timeout y graceful timeout configurables por entorno (2, 60 s y 30 s por defecto). Su access log va a stdout sin IP, referer, user agent ni query string, y una clase de logger propia reemplaza UID y token de `/accounts/reset/…/…/` por `<oculto>`.

### Keepalive de Supabase

Supabase pausa los proyectos gratuitos tras un período sin actividad. Sin infraestructura nueva, `.github/workflows/keepalive.yml` hace cada 3 días un `GET` a la URL de la variable de repositorio `HEALTHCHECK_URL`; cada consulta ejecuta `SELECT 1` en la base. Si la variable no está definida, el job termina sin error; si la app responde 503 o no responde, el job falla y GitHub lo notifica. GitHub desactiva los workflows programados de repositorios sin actividad durante 60 días, así que conviene revisar la pestaña Actions si el repo queda quieto mucho tiempo. También puede ejecutarse a mano con `workflow_dispatch`.

### Logging

`LOGGING` envía todo a stdout, que Railway conserva sin servicios extra, con el formato `fecha nivel logger mensaje`. `LOG_LEVEL` regula `django` y los loggers propios bajo `apps`; `django.request` y `django.security` se mantienen en `WARNING` o más, de modo que un 500 se registra con su traceback aunque no exista `ADMINS`. Los mensajes propios sólo llevan identificadores técnicos (endpoint, clase de error, código HTTP o del proveedor, `usuario_id`) y nunca cuerpos de email, tokens, contraseñas, destinatarios ni secretos. En tests el nivel por defecto es `WARNING` y la consola usa `NullHandler`; los registros se verifican con `assertLogs`.

## Concurrencia e integridad operativa

Las mutaciones que comparten filas respetan el orden `Cliente → Moto → Servicio → Tipo/Mantenimiento → Seguimiento`. Una operación bloquea solamente las filas necesarias; si no necesita una entidad anterior, puede comenzar en el siguiente nivel sin invertir el orden. Cuando hay varias filas del mismo tipo se ordenan por PK. Los locks sobre Cliente, Moto, Servicio y Seguimiento usan `FOR NO KEY UPDATE` cuando corresponde para evitar bloquear innecesariamente referencias foráneas.

Crear una Moto bloquea y revalida su Cliente. Archivar o restaurar Cliente/Moto y editar datos que compiten con esos estados ocurre dentro de `transaction.atomic`. Crear un Servicio prelee el propietario, bloquea Cliente y Moto por separado y aborta si la relación cambió; editar o cancelar bloquea Moto y luego Servicio, y la sincronización bloquea después los mantenimientos ordenados. Las acciones de seguimiento bloquean Cliente, Moto, TipoMantenimiento y finalmente Seguimiento. Así no se depende de locks implícitos producidos por joins.

## Usuarios y recuperación de acceso

La aplicación conserva `django.contrib.auth.models.User`; no define `AUTH_USER_MODEL`, perfiles paralelos ni tablas propias de roles. Un usuario es Propietario si es superuser o pertenece al Group `Propietario`. Cualquier otro usuario autenticado tiene rol Usuario. `is_staff` no interviene en esta decisión.

La app `usuarios` centraliza formularios, autorización, reglas de gestión y emails. Conserva `auth.User`; su único modelo propio es el contador técnico `LimiteAutenticacion`. Sus vistas administrativas validan el rol en backend: una persona no autenticada vuelve al login y una autenticada sin rol Propietario recibe HTTP 403. Las mutaciones de estado e invitación aceptan exclusivamente POST con CSRF. Los superusers quedan protegidos frente a Propietarios normales y nunca se permite desactivar o degradar al último Propietario activo.

El alta guarda un `User` activo con contraseña no usable y, una vez cerrada la transacción, intenta enviar la invitación. Se reutilizan `default_token_generator`, UID en base64 y `PasswordResetConfirmView`; no se persisten tokens. Reenviar o cambiar el email de una cuenta pendiente renueva la contraseña no usable e invalida el enlace previo. Un fallo del proveedor conserva la cuenta pendiente y permite reintentar sin exponer detalles técnicos.

La recuperación pública usa las vistas y validadores de Django y responde de la misma manera para un correo válido, inexistente o inactivo. El email se consulta con la misma expresión normalizada que protege la base. Formularios y servicios anticipan duplicados, mientras un índice único parcial sobre `LOWER(TRIM(auth_user.email))` resuelve la carrera definitiva; una `IntegrityError` de ese índice se transforma en un error de campo sin detalles SQL. La migración bloquea `auth_user`, aborta sin modificar datos si encuentra duplicados normalizados y permite emails vacíos históricos. El timeout es configurable y por defecto dura 24 horas. Cambiar el email propio exige la contraseña actual; `PasswordChangeView` mantiene la sesión mediante el mecanismo oficial de Django.

Login y recuperación reservan cada intento antes de autenticar o enviar email. El login normal y `/admin/login/` comparten las mismas reglas, por lo que el admin no queda como vía alternativa sin protección. Existen buckets separados por IP e identificador normalizado, almacenados sólo como HMAC-SHA256 con `SECRET_KEY`; una restricción única y `select_for_update` permiten varios workers sin Redis. Login usa 20 intentos por IP y 10 por identificador cada 15 minutos; recuperación usa 10 por IP y 5 por email cada hora. Todos los valores son settings configurables. Un exceso responde HTTP 429 con `Retry-After` y texto neutro. Un fallo de base durante el flujo protegido responde HTTP 503 con `Retry-After: 60`, registra sólo endpoint y clase del error y no continúa al backend de autenticación o email. Un login válido devuelve únicamente sus propias reservas; recuperación consume el intento exista o no la cuenta. Las ventanas vencidas se reinician bajo lock y el comando `limpiar_limites_autenticacion` permite purgar filas antiguas sin cron ni worker.

El transporte se selecciona por entorno: desarrollo imprime emails en consola, tests usa memoria y producción sigue `Django email API → BrevoEmailBackend → SDK brevo-python → Brevo HTTPS API`. Invitaciones conserva `EmailMultiAlternatives` y recuperación conserva `PasswordResetView`; ninguna vista conoce a Brevo. El backend usa `BREVO_FROM_EMAIL` y `BREVO_FROM_NAME` como remitente de producción, admite texto y HTML y no registra cuerpos, tokens, destinatarios ni `BREVO_API_KEY`. La configuración prevista usa el remitente verificado `MotoService <servicemoto09@gmail.com>`. Ante un rechazo registra solamente la clase, el código HTTP y el código normalizado del proveedor, sin conservar headers, cuerpos ni mensajes potencialmente sensibles. Los enlaces absolutos se crean desde el request, por lo que `SECURE_PROXY_SSL_HEADER` preserva HTTPS detrás de Railway. Ningún HTML de cuenta, usuarios o recuperación entra en la caché PWA.

## Cálculo de mantenimientos

La fuente de verdad está en `apps/mantenimientos/services.py`. Ese servicio de dominio suma meses calendario, selecciona el último mantenimiento válido por moto y tipo, calcula los límites de fecha y kilometraje y devuelve estados derivados. Dashboard, alertas y ficha de moto consumen el mismo resultado y no repiten reglas en vistas o templates.

Solo reinicia un ciclo un `MantenimientoRealizado` asociado a un servicio `FINALIZADO` cuya fecha no sea futura. Los servicios `ABIERTO` y `CANCELADO` se conservan en el historial, pero no intervienen en este cálculo. El último registro se decide por `Servicio.fecha`, con desempate estable por identificadores.

Las alertas no se persisten. Se calculan al abrir las pantallas usando tres consultas principales: tipos activos configurados, motos activas con su cliente actual activo y mantenimientos válidos con sus relaciones precargadas. El agrupamiento por `(moto_id, tipo_id)` se realiza en memoria para evitar N+1. No se requieren caché, cron, workers, Redis ni Celery.

## Seguimiento de alertas

La app `notificaciones` consume las alertas derivadas por `mantenimientos` y les superpone el seguimiento humano. La dependencia es unidireccional: `notificaciones` usa el servicio técnico de `mantenimientos`; el cálculo técnico no conoce los estados de contacto.

Una alerta técnica (`PROXIMO` o `VENCIDO`) y su seguimiento son conceptos distintos. Contactar, posponer o acordar un turno no cambia el estado técnico. El dashboard conserva los conteos técnicos y construye su cola de atención con el estado humano efectivo.

La superposición se realiza en lote: primero se calculan las alertas, luego se consultan todos los seguimientos relevantes y se combinan en memoria por `(mantenimiento_base_id, cliente_id)`. Los eventos sólo se cargan en la vista de historial. De este modo, las cards del dashboard, el listado y la ficha de moto no generan consultas por alerta.

Cada mutación recalcula y bloquea la moto y la regla dentro de `transaction.atomic`, comprueba que el mantenimiento base enviado como referencia siga siendo el ciclo actual, bloquea o crea el seguimiento y registra su evento en la misma transacción. Esto evita aplicar una acción abierta en una página vieja a un ciclo nuevo.

WhatsApp se integra exclusivamente mediante un enlace `wa.me` generado en el servidor con el propietario actual y un mensaje precargado. No hay API, envío automático ni llamada saliente desde el backend. Abrir el enlace tampoco registra contacto: el usuario debe ejecutar explícitamente la acción POST correspondiente.

El admin de Django permite listar, buscar, filtrar y consultar seguimientos y eventos, pero no crearlos, editarlos ni eliminarlos. Todas las mutaciones continúan pasando por los servicios de dominio y sus transacciones.

## Exportaciones y backups

La app `exportaciones` lee los datos existentes mediante QuerySets explícitos y genera CSV o Excel completamente en memoria. El flujo es `Django → memoria → navegador`: los archivos no se escriben en `static`, `media` ni en el filesystem persistente de Railway. La pantalla, instrucciones de backup, todos los CSV y el Excel exigen `propietario_required`: anónimos vuelven al login, Usuarios reciben HTTP 403 y Propietarios/superusers acceden. Los enlaces se ocultan para Usuarios, pero la autorización real permanece en cada view. Las descargas se entregan como adjuntos privados sin caché y neutralizan texto que una planilla podría interpretar como fórmula.

CSV y Excel son exportaciones legibles, no backups recuperables. El backup técnico sigue el flujo `management command → pg_dump → archivo local`: se ejecuta deliberadamente fuera de HTTP, limita el dump al schema `public`, usa formato custom y valida el archive con `pg_restore --list`. Las credenciales provienen de la conexión Django mediante variables `PG*`; la contraseña no forma parte de los argumentos del proceso. La restauración se documenta y se prueba primero sobre una base PostgreSQL nueva, nunca automáticamente sobre producción.

## Multi-taller futuro

La aplicacion nace para un unico taller. Aun asi, se documenta la posibilidad futura de soportar:

```text
Taller
├ Usuarios
├ Clientes
├ Motos
└ Servicios
```

No se implementa multi-tenant en esta fase para evitar complejidad prematura.
