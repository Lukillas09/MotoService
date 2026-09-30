# Sistema de interfaz y experiencia de usuario

La interfaz de MotoService está orientada a responder primero qué requiere atención, sobre qué moto, para qué cliente y qué acción puede realizar el taller. Usa Django Templates, Bootstrap 5, HTMX y JavaScript pequeño; no funciona como una SPA.

## Sistema visual

Los tokens principales viven en `static/css/app.css`. El azul `#075ee5` identifica acciones y navegación; rojo, naranja, verde, celeste y violeta comunican estados. Las superficies usan blanco y grises azulados suaves, con bordes discretos, radios de 10 a 24 px según jerarquía y dos niveles de sombra. La tipografía utiliza la pila del sistema para evitar descargas adicionales.

Los estados técnicos y humanos permanecen separados:

- técnico: vencido, próximo, al día, sin registro, datos insuficientes y no configurado;
- seguimiento: pendiente, contactado, pospuesto, turno acordado y no interesado.

Las clases de badges se resuelven de forma centralizada mediante los filtros de `apps/core/templatetags/formato.py`. Los templates no asignan colores distintos al mismo estado.

## Navegación responsive

En escritorio se muestra una sidebar fija con las áreas principales y una topbar con búsqueda global y contexto de sesión. Mi cuenta está disponible para todas las personas autenticadas y Usuarios aparece solo para Propietarios. En tablet y móvil, hasta 991 px, la sidebar desaparece y se reemplaza por una navegación inferior con Inicio, Clientes, la acción central Nuevo servicio, Motos y Más. “Más” abre un offcanvas Bootstrap con Mi cuenta, Usuarios cuando corresponde, Servicios, Mantenimientos, reglas, Exportaciones, búsqueda y cierre de sesión.

Los KPIs usan una grilla 4×1 en escritorio y 2×2 en anchos menores. Las filas de servicios, mantenimientos e historial pasan progresivamente a dos columnas y luego a cards verticales. Los formularios agrupan campos por tarea y la selección de mantenimientos usa controles táctiles completos.

## Motos sin fotos

`static/images/moto-generic.png` es la representación estándar en dashboard, listados, ficha, contexto de servicio y paneles de seguimiento. Conserva transparencia y proporciones mediante `object-fit: contain`; no cambia según marca, modelo o color. No hay modelos para fotos, almacenamiento media, logos de fabricantes, scraping ni solicitudes a servicios externos.

El brand mark de MotoService vive en `static/icons/motoservice-mark.png`. La interfaz carga una variante optimizada de 96 px y favicon/PWA usan derivados del mismo master. Los iconos oficiales `moto-solid` y `service-gear` forman parte del sprite `static/icons/ui.svg`, heredan `currentColor` y mantienen el mismo viewBox. Cada uno conserva una sola geometría para navegación, KPIs, hero, botones y estados vacíos; el tamaño y la opacidad cambian únicamente mediante CSS.

## Interacción, accesibilidad y movimiento

Cards, botones, inputs, badges y navegación usan transiciones de 160 a 220 ms. Los offcanvas conservan la transición accesible de Bootstrap. `prefers-reduced-motion: reduce` reduce animaciones y transiciones globalmente.

La interfaz conserva foco visible, labels asociados, enlace para saltar al contenido, regiones `aria-live`, textos accesibles para acciones de icono y destinos táctiles de al menos 44 px en las acciones principales. El contraste se apoya en texto oscuro y fondos suaves; el color no es la única identificación porque cada badge mantiene su etiqueta.

## Guía de uso

`/guia/` es un centro de ayuda privado integrado en el shell normal. Está disponible desde la sidebar y desde “Más” en móvil. La portada presenta diez categorías en cards y un filtro en JavaScript vanilla sobre títulos, descripciones y palabras clave; sin JavaScript todas las categorías y tutoriales siguen siendo enlaces normales.

Los tutoriales limitan el ancho de lectura, apilan pasos en móvil, reutilizan los badges reales y ofrecen componentes de tip e importante. Las preguntas frecuentes usan el accordion de Bootstrap y muestran las respuestas expandidas mediante `noscript`. Las capturas se cargan únicamente en su tutorial, usan WebP, dimensiones explícitas, `loading="lazy"` y texto alternativo descriptivo. Su procedencia y privacidad se documentan en `docs/guia.md`.

## Usuarios y pantallas de acceso

El listado de usuarios utiliza cards adaptativas en lugar de una tabla horizontal. Cada card muestra identidad, username, email, rol y estado (`Activo`, `Invitación pendiente` o `Inactivo`) y conserva botones táctiles de al menos 44 px. Las acciones de desactivar y reenviar invitación piden confirmación y se envían como formularios POST.

Mi cuenta reutiliza el shell privado y agrupa identidad, rol, perfil y cambio de contraseña. Login, solicitud de recuperación, confirmación y resultado comparten el shell público de acceso. Los campos usan labels reales y `autocomplete` para username, email, contraseña actual y contraseña nueva. Los mensajes públicos de recuperación nunca confirman si un correo existe.

## PWA y privacidad

El manifest ofrece iconos PNG de 192 y 512 px, variantes maskable en ambos tamaños y Apple Touch Icon. El service worker `motoservice-static-v13` precarga únicamente CSS, JavaScript, manifest e imágenes propias. Sólo responde desde caché a rutas bajo `/static/`; las páginas autenticadas y los datos privados, incluidas `/guia/`, `/usuarios/`, `/cuenta/` y las vistas de recuperación, siempre dependen de la red y del control de acceso de Django.
