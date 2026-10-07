# Modelo de datos

Las Fases 1 a 4 implementan clientes, motos, servicios, trabajos realizados, reglas configurables, alertas técnicas derivadas y seguimiento de contacto.

## Cliente

Representa a la persona propietaria o responsable de una o más motos.

Campos:

- `nombre`: texto obligatorio, con espacios internos normalizados;
- `apellido`: texto opcional;
- `telefono`: texto opcional, sin restricción de unicidad;
- `email`: email opcional, validado por Django y no único;
- `direccion`: texto opcional;
- `observaciones`: texto opcional;
- `activo`: estado para archivado lógico;
- `creado_en` y `actualizado_en`: fechas de auditoría automáticas.

El orden predeterminado es por apellido y nombre. Un cliente archivado no aparece en el listado activo, pero continúa disponible en su ficha y puede restaurarse.

## Moto

Representa una moto vinculada a un cliente.

Campos:

- `cliente`: relación obligatoria con `Cliente` mediante `ForeignKey`;
- `patente`: texto opcional y único cuando existe;
- `marca` y `modelo`: textos obligatorios;
- `anio`: entero opcional entre 1900 y el año actual más uno;
- `cilindrada_cc`: entero positivo opcional expresado en cc;
- `color`: texto opcional;
- `kilometraje_actual`: último kilometraje conocido por el taller, entero positivo opcional;
- `numero_chasis` y `numero_motor`: textos opcionales;
- `observaciones`: texto opcional;
- `activo`: estado para archivado lógico;
- `creado_en` y `actualizado_en`: fechas de auditoría automáticas.

La patente se normaliza en el modelo: se convierte a mayúsculas y se eliminan espacios y guiones. Una patente vacía se guarda como `NULL`, lo que permite registrar varias motos sin patente. El orden predeterminado es por marca y modelo.

## Relación Cliente → Moto

La relación es uno a muchos:

```text
Cliente 1 ─── N Moto
```

Se utiliza `related_name="motos"`, por lo que las motos se consultan con `cliente.motos.all()`. La relación usa `on_delete=PROTECT`: no se puede borrar físicamente un cliente que tenga motos asociadas.

El archivado de un cliente no modifica sus motos. Las motos conservan explícitamente su estado activo o archivado y siguen accesibles desde sus propias fichas. Para agregar una moto nueva a un cliente archivado primero se debe restaurar al cliente.

## Servicio

Representa una visita o trabajo efectuado sobre una moto.

Campos principales:

- `moto`: relación protegida con la moto y no modificable después del alta;
- `cliente`: relación protegida que conserva al propietario existente al crear el servicio;
- `fecha`: fecha del trabajo, con soporte para carga histórica;
- `kilometraje`: lectura opcional de esa visita;
- `estado`: `ABIERTO`, `FINALIZADO` o `CANCELADO`;
- `trabajos_adicionales` y `observaciones`: detalle libre;
- `precio_total`: decimal opcional y no negativo;
- `creado_por`: usuario de Django que registró el servicio, conservado mientras exista;
- `creado_en` y `actualizado_en`: fechas de auditoría.

Un servicio nuevo toma su cliente desde `moto.cliente` en el servidor. Ese dato no cambia si la moto se transfiere posteriormente. Solo se admiten servicios nuevos para una moto activa cuyo cliente actual también esté activo.

Un kilometraje mayor actualiza `Moto.kilometraje_actual`. Un valor menor requiere confirmación explícita en el formulario y queda guardado como lectura histórica, sin reducir el último kilometraje conocido. Los servicios cancelados se conservan y nunca actualizan ese valor.

## TipoMantenimiento

Es el catálogo configurable de trabajos que el taller puede seleccionar al registrar un servicio. Contiene:

- `nombre` y `descripcion`;
- `activo`: archivado lógico del tipo;
- `genera_recordatorio`: indica si participa en cálculos operativos;
- `intervalo_meses`: ciclo temporal opcional, mayor o igual a uno;
- `intervalo_km`: ciclo por kilometraje opcional, mayor o igual a uno;
- `aviso_dias`: anticipación temporal no negativa, con valor inicial de 30;
- `aviso_km`: anticipación por kilometraje no negativa, con valor inicial de 0;
- `creado_en` y `actualizado_en`.

Un recordatorio activo requiere al menos un intervalo. Puede conservar sus intervalos al desactivarse para permitir pausarlo sin perder la configuración. Estas invariantes están protegidas por validación de Django y restricciones de PostgreSQL.

La Fase 2 cargó once trabajos habituales. La migración de Fase 3 conserva esas filas con `genera_recordatorio=False` y sin intervalos: el taller debe configurar sus reglas reales, sin valores inventados.

## MantenimientoRealizado

Relaciona un `Servicio` con un `TipoMantenimiento` y permite observaciones. La combinación de servicio y tipo es única, por lo que el mismo trabajo no puede registrarse dos veces en una visita.

```text
Cliente 1 ─── N Moto
Cliente 1 ─── N Servicio (propietario histórico)
Moto 1 ─── N Servicio
Servicio 1 ─── N MantenimientoRealizado N ─── 1 TipoMantenimiento
```

La relación desde servicio hacia sus trabajos usa `CASCADE` porque son parte del propio registro. Las relaciones históricas hacia moto, cliente y tipo de mantenimiento usan `PROTECT`.

## Estados derivados de mantenimiento

No existe una tabla de alertas. Para cada moto y tipo configurado se deriva uno de estos estados:

- `AL_DIA`: todos los límites calculables están fuera de sus ventanas de aviso;
- `PROXIMO`: al menos un límite entró en su ventana de aviso y ninguno venció;
- `VENCIDO`: se alcanzó o superó al menos un límite de fecha o kilometraje;
- `SIN_REGISTRO`: nunca hubo un mantenimiento válido de ese tipo para la moto;
- `DATOS_INSUFICIENTES`: existe un registro, pero no están los kilometrajes necesarios para una regla que depende solo de kilómetros.

Cuando una regla tiene fecha y kilometraje, se aplica el límite que ocurra primero con prioridad `VENCIDO > PROXIMO > AL_DIA`. Una dimensión calculable sigue siendo válida aunque falten datos para la otra. La fecha usa suma de meses calendario; el kilometraje parte exclusivamente del valor del último servicio que realizó ese tipo y lo compara con `Moto.kilometraje_actual`, que representa la última lectura conocida por el taller.

## SeguimientoMantenimiento

Persiste el estado operativo del contacto asociado a una alerta técnica. No guarda `PROXIMO`, `VENCIDO` ni otro estado técnico.

Campos principales:

- `mantenimiento_base`: `MantenimientoRealizado` que inicia el ciclo, protegido ante borrado;
- `cliente`: propietario contactado durante ese ciclo, protegido ante borrado;
- `estado`: `PENDIENTE`, `CONTACTADO`, `POSPUESTO`, `TURNO_ACORDADO` o `NO_INTERESADO`;
- `pospuesto_hasta` y `turno_para`: referencias opcionales exigidas por sus estados respectivos;
- `ultimo_contacto_en` y `ultimo_contacto_por`: auditoría del contacto explícito más reciente;
- `observaciones`: nota operativa actual;
- `actualizado_por`, `creado_en` y `actualizado_en`: auditoría del seguimiento.

La combinación `(mantenimiento_base, cliente)` es única. Esta clave separa dos situaciones que no deben heredar estado:

```text
nuevo MantenimientoRealizado -> nuevo ciclo -> seguimiento pendiente
mismo ciclo + nuevo propietario -> nuevo seguimiento pendiente
```

La ausencia de una fila equivale a `PENDIENTE` en la interfaz. Las lecturas nunca crean seguimientos. Un `CONTACTADO` sigue siendo accionable; una posposición o turno futuro queda fuera de la cola inmediata; al llegar su fecha vuelve a ser accionable mediante cálculo en lectura, sin modificar la base ni ejecutar tareas programadas. `NO_INTERESADO` sólo se aplica a esa combinación de ciclo y cliente.

## EventoSeguimientoMantenimiento

Conserva el historial de acciones de un seguimiento. Registra `CONTACTADO`, `POSPUESTO`, `TURNO_ACORDADO`, `NO_INTERESADO`, `REABIERTO` y `NOTA`, junto con usuario, nota, referencias de fecha y fecha de creación.

El evento usa `CASCADE` hacia su seguimiento porque forma parte de ese registro, mientras que el usuario usa `SET_NULL` para conservar el historial si la cuenta desaparece. No existe una interfaz normal de borrado. La actualización del estado actual y la creación de su evento se realizan en una única transacción.

```text
MantenimientoRealizado 1 ─── N SeguimientoMantenimiento N ─── 1 Cliente
SeguimientoMantenimiento 1 ─── N EventoSeguimientoMantenimiento
```

## Usuario de Django y roles

El acceso utiliza directamente `django.contrib.auth.models.User`. No existe un Custom User Model ni un modelo de perfil. Se reutilizan `username`, `first_name`, `last_name`, `email`, `password`, `is_active`, `is_staff` e `is_superuser`.

Los roles funcionales se derivan sin una tabla propia:

- `Propietario`: `is_superuser=True` o pertenencia al Group de Django `Propietario`;
- `Usuario`: cualquier usuario autenticado que no cumple la condición anterior.

Las cuentas creadas desde MotoService requieren un email único ignorando mayúsculas y espacios externos. Formularios y servicios mantienen la validación amigable, y un índice único funcional de PostgreSQL sobre `LOWER(TRIM(email))` es la garantía definitiva. El índice es parcial y excluye valores cuyo `TRIM` queda vacío, por lo que siguen siendo compatibles varias cuentas históricas sin email. Una cuenta invitada se guarda con `is_active=True` y contraseña no usable hasta que la persona abre el enlace y elige una contraseña. `is_active=False` representa una cuenta desactivada; nunca se elimina desde la interfaz.

La migración no corrige, elimina ni fusiona cuentas. Antes de crear el índice toma un lock de tabla en PostgreSQL y busca grupos normalizados duplicados; si existen, aborta con la cantidad de grupos y exige una corrección manual en un entorno controlado. Un superuser existente sin email conserva el acceso, ve el aviso en Mi cuenta y puede agregar uno.

`Servicio.creado_por`, `SeguimientoMantenimiento.ultimo_contacto_por`, `SeguimientoMantenimiento.actualizado_por` y `EventoSeguimientoMantenimiento.usuario` continúan apuntando al usuario de Django. Desactivar una cuenta no modifica esas relaciones ni el historial.

## LimiteAutenticacion

Es una tabla técnica para proteger login y recuperación en varios workers. Guarda `ambito`, `sujeto_hash`, `ventana_iniciada_en`, `intentos` y `expira_en`. La pareja `(ambito, sujeto_hash)` es única y `expira_en` está indexado. El sujeto es un HMAC-SHA256 con `SECRET_KEY`: nunca se persisten IP, username, email ni contraseña en claro. Las filas vencidas se reutilizan al volver a recibir el mismo sujeto o se eliminan mediante el comando administrativo de limpieza.

## Entidades futuras

- `Taller`: posible agrupación para soportar varios talleres en el futuro;
- `TallerUsuario`: posible vínculo explícito si en el futuro se implementa multi-taller;
