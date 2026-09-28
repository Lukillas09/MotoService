# Arquitectura

El proyecto usa un monolito Django modular:

```text
Django monolitico modular -> Railway -> Supabase PostgreSQL
```

Django concentra templates, autenticacion, reglas de negocio, vistas y admin en una sola aplicacion web. Las apps dentro de `apps/` separan responsabilidades sin convertir el sistema en microservicios.

La app `servicios` administra las visitas al taller y conserva una referencia histórica al cliente que era propietario al momento del registro. La app `mantenimientos` administra el catálogo, las reglas configurables, los trabajos realizados y el cálculo de próximos mantenimientos.

El alta y la edición de un servicio se ejecutan dentro de una transacción. La misma operación guarda el servicio, sincroniza sus mantenimientos y actualiza el último kilometraje conocido de la moto solo si el nuevo valor es mayor. El modelo bloquea la moto durante esa actualización para proteger el kilometraje ante registros concurrentes.

Railway sera el hosting de la aplicacion Django. Supabase se usara principalmente como PostgreSQL administrado en produccion.

## Producción

La configuración de producción exige `SECRET_KEY` y `DATABASE_URL`, mantiene `DEBUG=False`, requiere PostgreSQL con SSL y toma hosts y orígenes CSRF desde variables de entorno. Django confía en el encabezado HTTPS del proxy de Railway, redirige a HTTPS y marca como seguras las cookies de sesión y CSRF.

WhiteNoise sirve los estáticos generados por `collectstatic` con el backend comprimido y con manifiesto configurado mediante `STORAGES`. El service worker se publica desde la raíz requerida por su alcance, pero sólo intercepta solicitudes GET bajo `/static/`; las páginas autenticadas y los datos privados no se almacenan en caché. HSTS se habilitará al cerrar el despliegue, después de confirmar el dominio y HTTPS de extremo a extremo.

La arquitectura evita Redis, Celery, servicios adicionales y frontend separado mientras no exista una necesidad concreta. Esto reduce costos, complejidad operativa y mantenimiento.

Las vistas privadas usan Django Auth. Los listados y filtros conservan un fallback HTTP normal y HTMX se limita a reemplazar resultados o mostrar el contexto de la moto seleccionada.

## Usuarios y recuperación de acceso

La aplicación conserva `django.contrib.auth.models.User`; no define `AUTH_USER_MODEL`, perfiles paralelos ni tablas propias de roles. Un usuario es Propietario si es superuser o pertenece al Group `Propietario`. Cualquier otro usuario autenticado tiene rol Usuario. `is_staff` no interviene en esta decisión.

La app `usuarios`, que no tiene modelos, centraliza formularios, autorización, reglas de gestión y emails. Sus vistas administrativas validan el rol en backend: una persona no autenticada vuelve al login y una autenticada sin rol Propietario recibe HTTP 403. Las mutaciones de estado e invitación aceptan exclusivamente POST con CSRF. Los superusers quedan protegidos frente a Propietarios normales y nunca se permite desactivar o degradar al último Propietario activo.

El alta guarda un `User` activo con contraseña no usable y, una vez cerrada la transacción, intenta enviar la invitación. Se reutilizan `default_token_generator`, UID en base64 y `PasswordResetConfirmView`; no se persisten tokens. Reenviar o cambiar el email de una cuenta pendiente renueva la contraseña no usable e invalida el enlace previo. Un fallo del proveedor conserva la cuenta pendiente y permite reintentar sin exponer detalles SMTP.

La recuperación pública usa las vistas y validadores de Django, responde de la misma manera para un correo válido, inexistente o inactivo y evita envíos ambiguos cuando detecta duplicados históricos. El timeout es configurable y por defecto dura 24 horas. Cambiar el email propio exige la contraseña actual; `PasswordChangeView` mantiene la sesión mediante el mecanismo oficial de Django.

Desarrollo imprime emails en consola, tests usa memoria y producción usa SMTP configurado por entorno. Los enlaces absolutos se crean desde el request, por lo que `SECURE_PROXY_SSL_HEADER` preserva HTTPS detrás de Railway. Ningún HTML de cuenta, usuarios o recuperación entra en la caché PWA.

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

## Exportaciones y backups

La app `exportaciones` lee los datos existentes mediante QuerySets explícitos y genera CSV o Excel completamente en memoria. El flujo es `Django → memoria → navegador`: los archivos no se escriben en `static`, `media` ni en el filesystem persistente de Railway. Todos los endpoints requieren autenticación, se entregan como adjuntos privados sin caché y neutralizan texto que una planilla podría interpretar como fórmula.

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
