from django.contrib import admin

from .models import EventoSeguimientoMantenimiento, SeguimientoMantenimiento


class EventoSeguimientoInline(admin.TabularInline):
    model = EventoSeguimientoMantenimiento
    extra = 0
    can_delete = False
    fields = (
        "tipo_evento",
        "usuario",
        "nota",
        "pospuesto_hasta",
        "turno_para",
        "creado_en",
    )
    readonly_fields = fields
    ordering = ("creado_en", "pk")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SeguimientoMantenimiento)
class SeguimientoMantenimientoAdmin(admin.ModelAdmin):
    list_display = (
        "tipo_mantenimiento",
        "moto",
        "cliente",
        "estado",
        "pospuesto_hasta",
        "turno_para",
        "ultimo_contacto_en",
        "actualizado_en",
    )
    list_filter = ("estado",)
    search_fields = (
        "cliente__nombre",
        "cliente__apellido",
        "mantenimiento_base__servicio__moto__patente",
        "mantenimiento_base__tipo_mantenimiento__nombre",
    )
    readonly_fields = (
        "mantenimiento_base",
        "cliente",
        "estado",
        "pospuesto_hasta",
        "turno_para",
        "ultimo_contacto_en",
        "ultimo_contacto_por",
        "observaciones",
        "actualizado_por",
        "creado_en",
        "actualizado_en",
    )
    list_select_related = (
        "cliente",
        "mantenimiento_base__tipo_mantenimiento",
        "mantenimiento_base__servicio__moto",
        "ultimo_contacto_por",
        "actualizado_por",
    )
    inlines = (EventoSeguimientoInline,)

    @admin.display(
        description="mantenimiento",
        ordering="mantenimiento_base__tipo_mantenimiento__nombre",
    )
    def tipo_mantenimiento(self, obj):
        return obj.mantenimiento_base.tipo_mantenimiento.nombre

    @admin.display(
        description="moto",
        ordering="mantenimiento_base__servicio__moto__patente",
    )
    def moto(self, obj):
        return obj.mantenimiento_base.servicio.moto

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EventoSeguimientoMantenimiento)
class EventoSeguimientoMantenimientoAdmin(admin.ModelAdmin):
    list_display = (
        "creado_en",
        "tipo_evento",
        "seguimiento",
        "usuario",
        "pospuesto_hasta",
        "turno_para",
    )
    list_filter = ("tipo_evento", "creado_en")
    search_fields = (
        "seguimiento__cliente__nombre",
        "seguimiento__cliente__apellido",
        "seguimiento__mantenimiento_base__servicio__moto__patente",
        "seguimiento__mantenimiento_base__tipo_mantenimiento__nombre",
        "nota",
    )
    readonly_fields = (
        "seguimiento",
        "tipo_evento",
        "usuario",
        "nota",
        "pospuesto_hasta",
        "turno_para",
        "creado_en",
    )
    list_select_related = (
        "seguimiento__cliente",
        "seguimiento__mantenimiento_base__tipo_mantenimiento",
        "seguimiento__mantenimiento_base__servicio__moto",
        "usuario",
    )
    date_hierarchy = "creado_en"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
