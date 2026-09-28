# Guía de uso integrada

La guía vive en templates bajo `templates/guia/`. No utiliza base de datos, modelos, CMS ni servicios externos. Las rutas requieren autenticación y el service worker no almacena el HTML privado. La categoría “Usuarios y acceso” explica roles, invitaciones, Mi cuenta, recuperación y desactivación sin necesitar capturas adicionales.

## Capturas

Las capturas fueron tomadas de la aplicación real ejecutada localmente contra una base SQLite temporal y aislada. Esa base contenía exclusivamente datos ficticios:

- usuario `Operador Demo`;
- cliente `Cliente Demo`;
- moto `Moto de ejemplo Urbana 150`, patente `DEMO01`;
- teléfonos, emails y direcciones vacíos;
- un servicio y una regla creados sólo para representar una alerta.

No se usó Supabase ni información del entorno habitual. Antes de incorporarlas se revisaron visualmente para confirmar que no contienen datos personales reales.

Assets creados:

- `01-dashboard.webp`: Inicio y Requieren atención;
- `02-clientes-nuevo.webp`: formulario Nuevo cliente;
- `03-moto-nueva.webp`: formulario Nueva moto;
- `04-moto-ficha.webp`: ficha y acción Registrar servicio;
- `05-servicio-nuevo.webp`: formulario Nuevo servicio;
- `06-mantenimientos.webp`: alertas, filtros y estado técnico;
- `07-configuracion.webp`: regla de mantenimiento;
- `08-seguimiento.webp`: panel real de seguimiento;
- `09-exportaciones.webp`: CSV, Excel y backup.

## Captura pendiente

- `10-pwa-ios.webp`: Safari en un iPhone con el menú Compartir y “Agregar a Inicio” resaltado. Debe capturarse en un dispositivo real o simulador confiable, sin mostrar historial, favoritos, cuenta, dominio privado ni datos del taller. Hasta que exista, el template no renderiza ninguna imagen ni deja un recurso roto.

## Actualización

Cada entrada de `apps/core/guia.py` declara el nombre esperado y un texto alternativo. La vista comprueba que el archivo exista antes de ofrecerlo al template. Para reemplazar una captura, se debe conservar el encuadre legible, optimizarla como WebP y volver a revisar que sólo muestre información ficticia.

La FAQ también cubre que no hay registro público, por qué el email es necesario, cómo recuperar una contraseña y por qué desactivar una cuenta conserva el historial.
