"""Índice editorial de la guía; el contenido se mantiene en templates."""

TEMAS = (
    {
        "slug": "primeros-pasos",
        "titulo": "Primeros pasos",
        "descripcion": "Conocé el inicio y el recorrido de trabajo del taller.",
        "icono": "home",
        "keywords": "inicio dashboard atención alertas últimos servicios empezar",
    },
    {
        "slug": "clientes",
        "titulo": "Clientes",
        "descripcion": "Registrá, editá y archivá datos de tus clientes.",
        "icono": "users",
        "keywords": (
            "persona nombre teléfono contacto llamada whatsapp alta crear "
            "restaurar eliminar"
        ),
    },
    {
        "slug": "motos",
        "titulo": "Motos",
        "descripcion": "Agregá una moto y consultá su ficha e historial.",
        "icono": "moto-solid",
        "keywords": "patente propietario dueño transferencia kilometraje marca modelo",
    },
    {
        "slug": "servicios",
        "titulo": "Servicios",
        "descripcion": "Registrá trabajos, kilómetros y mantenimientos realizados.",
        "icono": "service-gear",
        "keywords": "service nuevo abierto finalizado cancelado precio aceite historial",
    },
    {
        "slug": "mantenimientos",
        "titulo": "Mantenimientos",
        "descripcion": "Configurá reglas y entendé cuándo corresponde volver.",
        "icono": "wrench",
        "keywords": (
            "alerta vencido próximo al día sin registro datos insuficientes "
            "no configurado meses kilómetros intervalos anticipación"
        ),
    },
    {
        "slug": "seguimiento",
        "titulo": "Seguimiento y WhatsApp",
        "descripcion": "Contactá al cliente, posponé avisos y registrá turnos.",
        "icono": "phone",
        "keywords": (
            "whatsapp pendiente contactado pospuesto turno acordado no interesado "
            "mensaje automático atención"
        ),
    },
    {
        "slug": "exportaciones",
        "titulo": "Exportaciones",
        "descripcion": "Descargá tus datos y conocé las copias de seguridad.",
        "icono": "download",
        "keywords": "csv excel backup copia seguridad descargar datos recuperación",
    },
    {
        "slug": "instalar",
        "titulo": "Instalar MotoService",
        "descripcion": "Accedé desde la pantalla de inicio de tu celular.",
        "icono": "plus",
        "keywords": (
            "pwa aplicación app iphone ios safari android chrome internet conexión "
            "pantalla principal"
        ),
    },
    {
        "slug": "usuarios-acceso",
        "titulo": "Usuarios y acceso",
        "descripcion": "Creá accesos privados y recuperá una contraseña por email.",
        "icono": "shield",
        "keywords": (
            "usuario propietario cuenta acceso invitación correo email contraseña "
            "recuperar desactivar reactivar"
        ),
    },
    {
        "slug": "preguntas-frecuentes",
        "titulo": "Preguntas frecuentes",
        "descripcion": "Respuestas rápidas a las dudas del día a día.",
        "icono": "help",
        "keywords": (
            "faq ayuda eliminar dueño alerta whatsapp contactado posponer turno "
            "cancelado descargar internet cuenta contraseña email usuario propietario"
        ),
    },
)

# Solo se muestran assets existentes. Los pendientes se documentan en docs/guia.md.
CAPTURAS = {
    "dashboard": (
        "01-dashboard.webp",
        "Inicio de MotoService con una alerta de ejemplo en Requieren atención.",
    ),
    "clientes": (
        "02-clientes-nuevo.webp",
        "Formulario Nuevo cliente con datos ficticios y campos de contacto.",
    ),
    "motos": (
        "03-moto-nueva.webp",
        "Formulario Nueva moto con propietario, patente, marca y modelo de ejemplo.",
    ),
    "ficha": (
        "04-moto-ficha.webp",
        "Ficha de una moto de ejemplo con propietario, kilometraje y Registrar servicio.",
    ),
    "servicios": (
        "05-servicio-nuevo.webp",
        "Formulario Nuevo servicio con fecha, estado y kilometraje de ejemplo.",
    ),
    "mantenimientos": (
        "06-mantenimientos.webp",
        "Alertas de mantenimiento con estados técnicos y filtros de seguimiento.",
    ),
    "configuracion": (
        "07-configuracion.webp",
        "Edición de una regla de ejemplo con intervalos y aviso anticipado.",
    ),
    "seguimiento": (
        "08-seguimiento.webp",
        "Panel de seguimiento con acciones de contacto, posposición y turno.",
    ),
    "exportaciones": (
        "09-exportaciones.webp",
        "Pantalla de exportaciones con descargas CSV por tipo de información.",
    ),
    "ios": (
        "10-pwa-ios.webp",
        "Menú Compartir de Safari con la opción Agregar a pantalla de inicio.",
    ),
}
