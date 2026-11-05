# Sistema de interfaz y experiencia de usuario

La interfaz de MotoService está orientada a responder primero qué requiere atención, sobre qué moto, para qué cliente y qué acción puede realizar el taller. Usa Django Templates, Bootstrap 5, HTMX y JavaScript pequeño; no funciona como una SPA.

## Sistema visual

El CSS propio vive en `static/css/`, dividido por responsabilidad y cargado sin build step mediante `<link>` en este orden desde `base.html`:

1. `tokens.css`: variables de color, superficies, bordes, radios, sombras, espacios y tiempos.
2. `base.css`: reset mínimo, tipografía, foco, marca, shell autenticado (sidebar, topbar, contenido), encabezados de página, shell público y versión.
3. `components.css`: cards, botones, modal de confirmación, formularios, filtros, badges, patente, moto genérica, cards de persona y contacto, detalle, estados vacíos, toasts, barra de carga y paginación.
4. `pages.css`: dashboard, búsqueda, ficha de moto, historial, alertas y seguimiento, formulario de servicio, exportaciones, login, guía y usuarios.
5. `responsive.css`: media queries por ancho y `prefers-reduced-motion`; va después de componentes y páginas para ganarles.
6. `utilities.css`: utilidades de una responsabilidad, al final.

No se usa `@import`, que encadenaría descargas. La alternativa de un único archivo sin `@import` sólo es posible concatenando, es decir, con un build step. Los seis `<link>` se piden en paralelo, WhiteNoise los sirve con hash y caché inmutable, y el service worker los precarga. La división se verificó con capturas píxel a píxel de 19 pantallas en escritorio y móvil, además de hover y offcanvas abiertos.

Quedan seis `!important`, todos necesarios:

- `.text-secondary` y `.shadow-sm` (`utilities.css`) reemplazan utilidades de Bootstrap que ya usan `!important`.
- Los cuatro de `prefers-reduced-motion` (`responsive.css`) tienen que ganarle a cualquier transición o animación.

Se quitaron diez que no hacían falta:

- El borde de `.card` y, con él, los de `.empty-state` y `.record-card:hover`, que sólo existían para ganarle.
- El `border: 0` de `.dashboard-hero` y el `box-shadow: none` de `.quick-search-card .input-group`, que no competían con ninguna regla.
- Los anchos y bordes de los offcanvas (`.follow-up-drawer`, `.mobile-more`), que ahora usan las variables `--bs-offcanvas-width` y `--bs-offcanvas-border-color` de Bootstrap.

Los tokens principales viven en `static/css/tokens.css`. El azul `#075ee5` identifica acciones y navegación; rojo, naranja, verde, celeste y violeta comunican estados. Las superficies usan blanco y grises azulados suaves, con bordes discretos, radios de 10 a 24 px según jerarquía y dos niveles de sombra. La tipografía utiliza la pila del sistema para evitar descargas adicionales.

Los estados técnicos y humanos permanecen separados:

- técnico: vencido, próximo, al día, sin registro, datos insuficientes y no configurado;
- seguimiento: pendiente, contactado, pospuesto, turno acordado y no interesado.

Las clases de badges se resuelven de forma centralizada mediante los filtros de `apps/core/templatetags/formato.py`. Los templates no asignan colores distintos al mismo estado.

## Navegación responsive

En escritorio se muestra una sidebar fija con las áreas principales y una topbar con búsqueda global y contexto de sesión. Mi cuenta está disponible para todas las personas autenticadas; Usuarios y Exportaciones aparecen solo para Propietarios. En tablet y móvil, hasta 991 px, la sidebar desaparece y se reemplaza por una navegación inferior con Inicio, Clientes, la acción central Nuevo servicio, Motos y Más. “Más” abre un offcanvas Bootstrap con Mi cuenta, Usuarios y Exportaciones cuando corresponde, Servicios, Mantenimientos, reglas, búsqueda y cierre de sesión.

La topbar muestra el nombre completo de la persona o, si no lo cargó, su username. El avatar usa las iniciales de nombre y apellido (máximo dos, en mayúscula y normalizadas para tildes) mediante el filtro `iniciales_usuario` de `formato.py`; sin nombre usa la inicial del username. El hint de la búsqueda global llega del servidor como “Ctrl K” y `app.js` lo cambia a “⌘K” en Mac y iOS.

La búsqueda global (`/buscar/`) muestra hasta 8 clientes activos, 8 motos activas y 8 servicios de cualquier estado. Los servicios se encuentran por patente, marca o modelo de la moto, cliente, teléfono, mantenimientos realizados, trabajos adicionales y observaciones, con la misma lógica de `Servicio.objects.buscar()` que usa el listado de servicios.

Los KPIs usan una grilla 4×1 en escritorio y 2×2 en anchos menores. Las filas de servicios, mantenimientos e historial pasan progresivamente a dos columnas y luego a cards verticales. Los formularios agrupan campos por tarea y la selección de mantenimientos usa controles táctiles completos.

## Motos sin fotos

`static/images/moto-generic.png` es la representación estándar en dashboard, listados, ficha, contexto de servicio y paneles de seguimiento. Conserva transparencia y proporciones mediante `object-fit: contain`; no cambia según marca, modelo o color. No hay modelos para fotos, almacenamiento media, logos de fabricantes, scraping ni solicitudes a servicios externos.

El brand mark de MotoService vive en `static/icons/motoservice-mark.png`. La interfaz carga una variante optimizada de 96 px y favicon/PWA usan derivados del mismo master. Los iconos oficiales `moto-solid` y `service-gear` forman parte del sprite `static/icons/ui.svg`, heredan `currentColor` y mantienen el mismo viewBox. Cada uno conserva una sola geometría para navegación, KPIs, hero, botones y estados vacíos; el tamaño y la opacidad cambian únicamente mediante CSS.

## Modo oscuro

Hay tres modos: **Automático** (sigue `prefers-color-scheme` del dispositivo y cambia en vivo si el sistema cambia), **Claro** y **Oscuro**. Se eligen en Mi cuenta → Apariencia y en el menú “Más” de móvil. La preferencia se guarda en `localStorage` (`motoservice-tema`) del navegador, no en la base: cada dispositivo puede tener la suya. Todo acceso a `localStorage` está en `try/catch`; si el almacenamiento está bloqueado, se usa Automático. Sin JavaScript el selector queda oculto y la app se ve en claro.

Un script inline mínimo en el `<head>` de `base.html`, antes del CSS, lee la preferencia y pone en `<html>`:

- `data-theme="light|dark"` cuando el modo está forzado (en Automático no está), y
- `data-bs-theme="light|dark"` siempre, con el tema resuelto.

`data-bs-theme` es el atributo que Bootstrap 5.3 usa para modales, offcanvas, dropdowns, formularios, accordion y alerts, y es también el único selector del tema en `tokens.css`. Así no hay un cuadro con el tema equivocado ni dos fuentes de verdad. `app.js` aplica los cambios del selector, sincroniza los dos selectores de la página, sigue los cambios del sistema en Automático y fuerza el `theme-color` cuando el modo está forzado. Durante el cambio agrega `.theme-switching`, que anula las transiciones (`!important` necesario), así los colores nunca se animan, con o sin `prefers-reduced-motion`.

`<meta name="color-scheme" content="light dark">` y dos `<meta name="theme-color">` con media query (`#075ee5` claro, `#0b1220` oscuro) ajustan los controles nativos y la barra del navegador. El manifest de la PWA conserva el color claro.

### Paleta

El tema oscuro sólo redefine tokens en `:root[data-bs-theme="dark"]`; ninguna regla de componentes o páginas depende del tema. Cada estado tiene tokens separados por rol, porque en oscuro un mismo azul no puede servir a la vez como texto sobre fondo oscuro y como fondo de texto blanco:

| Rol | Tokens | Claro | Oscuro |
| --- | --- | --- | --- |
| Fondo de página / cards / terciario | `--surface-secondary`, `--surface`, `--surface-tertiary` | `#f5f8fc` / `#ffffff` / `#edf3fa` | `#0b1220` / `#131d2e` / `#1b2840` |
| Títulos / texto / texto suave / secundario | `--color-ink`, `--color-text`, `--color-text-soft`, `--color-muted` | `#10213e` / `#263a59` / `#46607f` / `#5d6f8b` | `#eef3fb` / `#cdd8e8` / `#a9b8cf` / `#93a5c0` |
| Bordes decorativos / de controles / de acento | `--border-color`, `--border-strong`, `--border-accent` | `#dce6f2` / `#c9d7e8` / `#b9d2f5` | `#26364f` / `#5f7597` / `#3f6fb5` |
| Acento para texto, iconos y bordes | `--color-primary`, `--color-danger`, `--color-warning`, `--color-success`, `--color-info`, `--color-purple` | tonos saturados | tonos claros (`#7cb2ff`, `#ff7a8a`, …) |
| Texto de badges / fondo / borde | `--color-*-strong`, `--color-*-soft`, `--color-*-border` | texto oscuro sobre fondo pastel | texto claro sobre fondo oscuro teñido |
| Rellenos con texto blanco | `--color-primary-fill`, `--color-success-fill`, `--color-danger-fill`, `--color-warning-fill`, `--color-on-fill` | `#075ee5`, `#087a48`, `#c21f34`, `#a85b00` | `#2563d9`, `#087a48`, `#c21f34`, `#a85b00` |

Las sombras pasan a negro con más opacidad, el anillo de foco (`--focus-ring`) se aclara y el resplandor del fondo (`--page-glow`) se ajusta. Las barras translúcidas (sidebar, topbar, navegación inferior) usan `color-mix()` sobre `--surface`.

Quedan con colores fijos, porque ya son superficies oscuras de marca y se leen igual en ambos temas: el hero del dashboard, el panel azul del login, el botón central de la navegación móvil, el pie de la moto ilustrada y el bloque de comandos de backup.

La moto ilustrada es oscura, así que en el tema oscuro se apoya sobre un panel claro atenuado (`--moto-visual-bg`) en lugar de un fondo oscuro donde se perderían las ruedas. Los iconos SVG heredan `currentColor` y siguen al texto. Las capturas WebP de la guía siguen claras, pero `--screenshot-border` usa el borde fuerte para separarlas del fondo.

Las páginas autocontenidas (errores 4xx/5xx y offline) no cargan el CSS ni el JavaScript de la app: siguen el tema del sistema con una media query en sus estilos inline.

### Contraste

`scripts/verificar_contraste.py` calcula el contraste WCAG de 42 pares token/fondo en los dos temas: 4.5:1 para texto y 3:1 para bordes de controles, bordes de badges e iconos. Un test lo ejecuta en la suite y otro exige que cada token de color claro tenga su valor oscuro. El tema oscuro cumple todos los pares. En claro hay ocho excepciones documentadas en el script: el borde de inputs (`--border-strong`, 1.4:1) y los bordes pastel de los badges, que son decisiones previas de diseño y quedan para una revisión del tema claro.

Para esta entrega se ajustaron tres valores del tema claro por contraste:

- `--color-muted` pasó de `#687b98` (4.3:1 sobre blanco) a `#5d6f8b`.
- El botón de WhatsApp (`.btn-success`) usa `#087a48` (5.4:1 con texto blanco en lugar de 3.5:1).
- Seis grises intermedios casi iguales (`#36516f`, `#415b7b`, `#43566f`, `#526986`, `#53657d`, `#5140ad`) se unificaron en `--color-text-soft` o en el texto de badge correspondiente.

## Interacción, accesibilidad y movimiento

Cards, botones, inputs, badges y navegación usan transiciones de 160 a 220 ms. Los offcanvas conservan la transición accesible de Bootstrap. `prefers-reduced-motion: reduce` reduce animaciones y transiciones globalmente.

La interfaz conserva foco visible, labels asociados, enlace para saltar al contenido, regiones `aria-live`, textos accesibles para acciones de icono y destinos táctiles de al menos 44 px en las acciones principales. El contraste se apoya en texto oscuro y fondos suaves; el color no es la única identificación porque cada badge mantiene su etiqueta.

Las acciones con consecuencias (archivar cliente o moto, cancelar servicio, desactivar tipo de mantenimiento, marcar no interesado, desactivar usuario y reenviar invitación) usan un único modal Bootstrap, `templates/shared/confirm_modal.html`, incluido sólo en el shell autenticado. Cada form declara `data-confirm-message` (obligatorio, explica la consecuencia y si se puede deshacer) y opcionalmente `data-confirm-title`, `data-confirm-button` y `data-confirm-tone` (`danger` por defecto, `warning` o `primary`). Los tonos `danger` y `warning` usan `--color-danger-strong` y `--color-warning-strong` para que el texto blanco tenga contraste AA. `app.js` frena el submit en fase de captura (antes que HTMX), abre el modal y, al confirmar, reenvía el mismo form con `requestSubmit(submitter)`, así conserva el nombre y valor del botón y el estado `is-submitting`/`aria-busy`. El foco empieza en “Cancelar” en las acciones destructivas y en el botón de confirmar en las de tono `primary`; Escape, la cruz y el clic afuera cancelan y el foco vuelve al botón original. Los botones miden al menos 44 px. Si Bootstrap no cargó se usa `window.confirm()`, y sin JavaScript el form se envía directo: la autorización y la validación siguen en el backend.

Clientes, motos, servicios y alertas comparten `templates/shared/paginacion.html`: un `nav` con `aria-label`, la página actual marcada con `aria-current="page"`, enlaces Anterior/Siguiente y números de 44 px y el texto “Mostrando X–Y de Z”. En móvil sólo quedan Anterior, la página actual y Siguiente. Cada enlace es un `href` normal que conserva búsqueda y filtros; con HTMX reemplaza únicamente el contenedor de resultados y actualiza la URL. HTMX no guarda historial en `localStorage`, así que volver atrás recarga la página completa desde el servidor.

## Guía de uso

`/guia/` es un centro de ayuda privado integrado en el shell normal. Está disponible desde la sidebar y desde “Más” en móvil. La portada presenta diez categorías en cards y un filtro en JavaScript vanilla sobre títulos, descripciones y palabras clave; sin JavaScript todas las categorías y tutoriales siguen siendo enlaces normales.

Los tutoriales limitan el ancho de lectura, apilan pasos en móvil, reutilizan los badges reales y ofrecen componentes de tip e importante. Las preguntas frecuentes usan el accordion de Bootstrap y muestran las respuestas expandidas mediante `noscript`. Las capturas se cargan únicamente en su tutorial, usan WebP, dimensiones explícitas, `loading="lazy"` y texto alternativo descriptivo. Su procedencia y privacidad se documentan en `docs/guia.md`.

## Usuarios y pantallas de acceso

El listado de usuarios utiliza cards adaptativas en lugar de una tabla horizontal. Cada card muestra identidad, username, email, rol y estado (`Activo`, `Invitación pendiente` o `Inactivo`) y conserva botones táctiles de al menos 44 px. Las acciones de desactivar y reenviar invitación piden confirmación y se envían como formularios POST.

Mi cuenta reutiliza el shell privado y agrupa identidad, rol, perfil y cambio de contraseña. Login, solicitud de recuperación, confirmación y resultado comparten el shell público de acceso. Los campos usan labels reales y `autocomplete` para username, email, contraseña actual y contraseña nueva. Los mensajes públicos de recuperación nunca confirman si un correo existe.

## PWA y privacidad

El manifest ofrece iconos PNG de 192 y 512 px, variantes maskable en ambos tamaños y Apple Touch Icon.

El service worker se sirve en `/service-worker.js` desde una vista de `core` que renderiza `templates/pwa/service-worker.js`, con `Content-Type: application/javascript` y `Cache-Control: no-cache`, sin sesión ni context processors. Como se publica en la raíz, su alcance ya es todo el sitio y no necesita `Service-Worker-Allowed`. La lista de precarga vive en `apps/core/pwa.py` y se resuelve con `static()`, la misma función de `{% static %}`: en producción toma las URLs con hash de `CompressedManifestStaticFilesStorage`. El nombre de caché es `motoservice-<versión>-<hash>`, donde el hash cubre esas URLs, el contenido de cada archivo y los templates de la página offline, así que cambia sólo cuando cambia algo precargado. `activate` borra las cachés anteriores.

Estrategia:

- GET bajo `/static/`: cache-first.
- Navegaciones (`request.mode === "navigate"`): siempre a la red y nunca se guardan. Si la red falla, se responde con la página offline precargada.
- Todo lo demás (POST, HTMX, otros orígenes, cualquier HTML): el service worker no interviene.

`/offline/` es pública, se renderiza sin request y no contiene datos del usuario ni del taller. Reutiliza `error_base.html` (estilos inline y el logo precargado) y ofrece “Reintentar”, un enlace a la misma URL que funciona sin JavaScript.

Las páginas autenticadas y los datos privados, incluidas la guía, Usuarios, Mi cuenta, recuperación de contraseña, exportaciones y las respuestas HTMX, nunca entran en la caché y siempre dependen de la red y del control de acceso de Django.
