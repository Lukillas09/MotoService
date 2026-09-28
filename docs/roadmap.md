# Roadmap

## Fase 0 — Implementada

Base tecnica: Django, settings por entorno, apps iniciales, templates, PWA, deploy preparado y tests minimos.

## Fase 1 — Implementada

Gestión autenticada de clientes y motos: modelos, relación protegida, alta, listado, detalle, edición, archivado/restauración y búsqueda responsive con HTMX.

## Fase 2 — Implementada

Servicios e historial del taller: alta y edición transaccional, estados, cancelación sin borrado, kilometraje histórico, trabajos estructurados, filtros y búsqueda, ficha completa e historial por moto.

## Fase 3 — Implementada

Reglas configurables por meses y kilómetros, cálculo centralizado de estados, alertas operativas con filtros y HTMX, conteos y prioridades en dashboard, estado completo en la ficha de moto e interfaz para administrar el catálogo sin borrado físico.

## Fase 4 — Implementada

Seguimiento humano separado de las alertas técnicas: estados por ciclo y propietario, historial de eventos, contacto explícito, posposición, turno acordado, no interesado y reapertura. Incluye cola operativa derivada sin cron, integración manual con WhatsApp mediante `wa.me`, filtros y HTMX, dashboard y ficha de moto, administración, constraints, transacciones atómicas y tests de ciclo y propietario.

## Fase 4.1 — Implementada

Saneamiento y preparación para producción: auditoría de dominio, autenticación, URLs, consultas, dependencias, PWA y documentación; configuración moderna de estáticos con WhiteNoise; validación estricta de secretos; páginas de error seguras y pruebas de regresión. No requirió cambios de modelos ni migraciones.

## Fase 5 — Implementada

Exportaciones autenticadas de datos operativos en CSV y Excel, con protección de datos históricos, fórmulas y caché. Incluye backup manual recuperable del schema PostgreSQL mediante `pg_dump`, validación con `pg_restore`, checksum SHA-256 y documentación de restauración segura.

## Fase 6 — Implementada

Rediseño final UX/UI responsive: sistema visual con tokens y estados consistentes, shell de escritorio con sidebar y topbar, navegación inferior móvil, dashboard operativo, fichas y listados adaptativos, formularios táctiles, panel lateral de seguimiento y timeline. Incluye representación propia de motos sin fotografías, accesibilidad y movimiento reducido, estados vacíos, feedback HTMX, login y páginas de error renovadas, además del cierre PWA con iconos PNG/maskable y caché estática sin datos privados.

## Mejora post-lanzamiento — Guía de uso — Implementada

Centro de ayuda autenticado con diez categorías, búsqueda local, pasos reutilizables, tips, avisos importantes, FAQ accesible, navegación desktop/mobile y ayuda contextual en reglas, seguimiento y exportaciones. El contenido se versiona con el código y no agrega modelos, CMS ni dependencias.

## Mejora post-lanzamiento — Usuarios y recuperación — Implementada

Gestión privada sobre Django Auth sin Custom User Model: roles Propietario/Usuario, alta por invitación, contraseña elegida por cada persona, recuperación por email, Mi cuenta, cambio de contraseña, desactivación/reactivación y protección del último Propietario y de superusers. Incluye backend de email por entorno, Resend vía API HTTPS en producción, respuesta antienumeración, navegación responsive, guía y tests de seguridad. No agrega tablas ni registro público.
