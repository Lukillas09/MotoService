# Backups PostgreSQL

## Exportación y backup no son lo mismo

Los CSV y el Excel completo sirven para consultar, analizar y conservar una copia legible de los datos operativos. No contienen toda la estructura técnica necesaria para reconstruir exactamente la aplicación.

El backup PostgreSQL conserva tablas, relaciones, constraints y datos del schema de la aplicación. MotoService lo genera en formato custom de PostgreSQL mediante `pg_dump`. El dump se limita al schema `public`: no es una copia de todo el proyecto Supabase, de Supabase Auth, Storage ni de otros servicios externos.

## Requisitos

La computadora desde la que se crea el backup necesita:

- una copia del proyecto y su entorno Python;
- la conexión PostgreSQL configurada para Django;
- las herramientas cliente `pg_dump` y `pg_restore` disponibles en `PATH`;
- acceso de red y permisos de lectura sobre la base.

Conviene usar herramientas cliente de la misma versión mayor del servidor o una versión compatible. El comando reutiliza host, puerto, usuario, base, contraseña y `sslmode` desde la conexión activa de Django. La contraseña se entrega a `pg_dump` mediante el entorno del proceso y no aparece en sus argumentos.

## Crear un backup

Ejecutar desde una computadora administrativa o un entorno operativo controlado:

```text
python manage.py backup_database --output-dir "/ruta/privada/MotoService"
```

Si no se indica un destino, se usa `backups/` dentro del directorio actual. Esa carpeta está ignorada por Git, pero sigue siendo responsabilidad del operador mover los archivos a almacenamiento privado y persistente.

También se puede indicar el archivo exacto:

```text
python manage.py backup_database --output "/ruta/privada/motoservice_manual.dump"
```

El comando no sobrescribe archivos existentes. `--force` permite reemplazarlos de forma explícita; la copia anterior se conserva si `pg_dump` o la validación fallan antes del reemplazo.

## Qué genera y cómo lo valida

El proceso:

1. comprueba que Django esté conectado a PostgreSQL;
2. localiza `pg_dump` y `pg_restore`;
3. ejecuta `pg_dump` con formato custom, schema `public`, `--no-owner` y `--no-acl`;
4. comprueba que el archivo exista y no esté vacío;
5. ejecuta `pg_restore --list` para verificar que el archive pueda leerse;
6. calcula SHA-256;
7. genera un archivo compañero terminado en `.dump.sha256`.

`pg_restore --list` no restaura ni modifica la base. Si `pg_dump` o la validación fallan, el comando no presenta el resultado como válido y elimina el archivo parcial.

## Verificar una copia trasladada

Conservar siempre juntos:

```text
motoservice_2026-09-24_163000.dump
motoservice_2026-09-24_163000.dump.sha256
```

Después de copiar ambos archivos, recalcular SHA-256 con una herramienta del sistema y compararlo con el valor guardado. También se puede volver a comprobar la estructura sin restaurar:

```text
pg_restore --list "/ruta/privada/motoservice_2026-09-24_163000.dump"
```

Que `pg_dump` termine y `pg_restore --list` funcione es una verificación básica. Un backup sólo se considera probado cuando también se completa una restauración de ensayo.

## Probar una restauración

Nunca usar producción como primer destino. El procedimiento seguro es:

1. crear una base PostgreSQL nueva y vacía destinada a pruebas;
2. configurar credenciales temporales para esa base sin escribirlas en el comando ni versionarlas;
3. restaurar el dump con `pg_restore`, apuntando exclusivamente a la base de prueba, por ejemplo:

   ```text
   pg_restore --exit-on-error --no-owner --no-acl --dbname=motoservice_restore_test "/ruta/privada/motoservice.dump"
   ```

   El host, puerto, usuario y contraseña deben configurarse mediante variables `PG*` temporales o una configuración local protegida, nunca incrustarse en el comando;
4. configurar temporalmente Django contra esa base;
5. ejecutar `python manage.py check`;
6. revisar `python manage.py showmigrations` y `python manage.py migrate --plan`;
7. iniciar la aplicación y hacer un smoke test de login, clientes, motos, servicios, mantenimientos y seguimientos;
8. eliminar la base de prueba cuando la validación haya terminado.

No usar `--clean` contra producción como primer paso. Una recuperación real requiere evaluar el incidente, preservar evidencias, confirmar el backup elegido y planificar una ventana de mantenimiento antes de modificar la base productiva.

## Custodia y frecuencia

El `.dump` es más sensible que un CSV o Excel. Puede contener datos de clientes, teléfonos, emails, historial, hashes de contraseñas y sesiones de Django. Debe guardarse cifrado o dentro de almacenamiento privado con acceso limitado. No enviarlo por canales públicos, no subirlo al repositorio y no dejarlo en Render (el plan free no tiene shell ni discos persistentes: el backup se corre siempre desde una PC controlada).

Realizar backups según el ritmo de cambios del taller y conservar varias copias históricas en ubicaciones controladas, por ejemplo una computadora administrativa, un disco externo y almacenamiento cloud privado. Esta fase no borra copias antiguas ni programa tareas automáticas.
