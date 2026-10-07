from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.clientes.models import (
    Cliente,
    expresion_telefono_normalizado,
    normalizar_telefono_busqueda,
)
from apps.motos.models import Moto, normalizar_patente
from apps.motos.services import (
    PropietarioMotoCambioDuranteBloqueo,
    bloquear_cliente_actual_y_moto,
)


class ServicioQuerySet(models.QuerySet):
    def con_detalle(self):
        return self.select_related(
            "moto",
            "moto__cliente",
            "cliente",
            "creado_por",
        ).prefetch_related("mantenimientos_realizados__tipo_mantenimiento")

    def buscar(self, termino):
        termino = (termino or "").strip()
        if not termino:
            return self

        queryset = self
        if any(caracter.isdigit() for caracter in termino):
            queryset = queryset.annotate(
                telefono_cliente_busqueda=expresion_telefono_normalizado(
                    F("cliente__telefono")
                )
            )

        filtros = Q()
        for parte in termino.split():
            filtro_parte = (
                Q(moto__marca__icontains=parte)
                | Q(moto__modelo__icontains=parte)
                | Q(cliente__nombre__icontains=parte)
                | Q(cliente__apellido__icontains=parte)
                | Q(cliente__telefono__icontains=parte)
                | Q(
                    mantenimientos_realizados__tipo_mantenimiento__nombre__icontains=parte
                )
                | Q(trabajos_adicionales__icontains=parte)
            )
            patente = normalizar_patente(parte)
            if patente:
                filtro_parte |= Q(moto__patente__icontains=patente)
            if any(caracter.isdigit() for caracter in parte):
                telefono = normalizar_telefono_busqueda(parte)
                if telefono:
                    filtro_parte |= Q(
                        telefono_cliente_busqueda__icontains=telefono
                    )
            filtros &= filtro_parte

        return queryset.filter(filtros).distinct()


class Servicio(models.Model):
    class Estado(models.TextChoices):
        ABIERTO = "ABIERTO", "Abierto"
        FINALIZADO = "FINALIZADO", "Finalizado"
        CANCELADO = "CANCELADO", "Cancelado"

    moto = models.ForeignKey(
        Moto,
        on_delete=models.PROTECT,
        related_name="servicios",
        verbose_name="moto",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="servicios",
        verbose_name="cliente atendido",
        help_text="Propietario de la moto al registrar el servicio.",
    )
    fecha = models.DateField("fecha", default=timezone.localdate)
    kilometraje = models.PositiveIntegerField(
        "kilometraje",
        blank=True,
        null=True,
        validators=(MinValueValidator(0),),
    )
    estado = models.CharField(
        "estado",
        max_length=12,
        choices=Estado.choices,
        default=Estado.FINALIZADO,
    )
    trabajos_adicionales = models.TextField("otros trabajos", blank=True)
    observaciones = models.TextField("observaciones", blank=True)
    precio_total = models.DecimalField(
        "precio total",
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        validators=(MinValueValidator(Decimal("0.00")),),
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="servicios_creados",
        verbose_name="creado por",
        blank=True,
        null=True,
    )
    creado_en = models.DateTimeField("creado el", auto_now_add=True)
    actualizado_en = models.DateTimeField("actualizado el", auto_now=True)

    objects = ServicioQuerySet.as_manager()

    class Meta:
        ordering = ("-fecha", "-pk")
        verbose_name = "servicio"
        verbose_name_plural = "servicios"
        constraints = (
            models.CheckConstraint(
                condition=Q(precio_total__isnull=True) | Q(precio_total__gte=0),
                name="servicio_precio_total_no_negativo",
            ),
        )

    def clean(self):
        super().clean()
        self.trabajos_adicionales = (self.trabajos_adicionales or "").strip()
        self.observaciones = (self.observaciones or "").strip()

        if self._state.adding and self.moto_id:
            try:
                moto = self.moto
            except Moto.DoesNotExist:
                return

            errores = {}
            if not moto.activo:
                errores["moto"] = "No se puede registrar un servicio en una moto archivada."
            if moto.cliente_id and not moto.cliente.activo:
                errores["moto"] = (
                    "No se puede registrar un servicio mientras el cliente esté archivado."
                )
            if errores:
                raise ValidationError(errores)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self._state.adding:
                if not self.moto_id:
                    self.full_clean()
                try:
                    cliente, moto = bloquear_cliente_actual_y_moto(self.moto_id)
                except (Moto.DoesNotExist, Cliente.DoesNotExist) as error:
                    raise ValidationError(
                        {"moto": "La moto seleccionada no existe."}
                    ) from error
                except PropietarioMotoCambioDuranteBloqueo as error:
                    raise ValidationError(
                        {
                            "moto": (
                                "La moto cambió de propietario mientras se registraba "
                                "el servicio. Revisá los datos e intentá nuevamente."
                            )
                        }
                    ) from error
                self.moto = moto
                self.cliente = cliente
            else:
                try:
                    moto_id_original = Servicio.objects.values_list(
                        "moto_id", flat=True
                    ).get(pk=self.pk)
                    moto = Moto.objects.select_for_update(no_key=True).get(
                        pk=moto_id_original
                    )
                    original = Servicio.objects.select_for_update(no_key=True).get(
                        pk=self.pk
                    )
                except (Servicio.DoesNotExist, Moto.DoesNotExist) as error:
                    raise ValidationError(
                        "El servicio ya no existe o su moto no está disponible."
                    ) from error
                errores = {}
                if original.moto_id != moto.pk:
                    errores["moto"] = (
                        "La moto del servicio cambió durante la operación. "
                        "Revisá los datos e intentá nuevamente."
                    )
                if self.moto_id != original.moto_id:
                    errores["moto"] = "La moto de un servicio existente no se puede cambiar."
                if self.cliente_id != original.cliente_id:
                    errores["cliente"] = (
                        "El cliente histórico de un servicio no se puede cambiar."
                    )
                if self.creado_por_id != original.creado_por_id:
                    errores["creado_por"] = (
                        "El usuario que creó el servicio no se puede cambiar."
                    )
                if errores:
                    raise ValidationError(errores)

            self.full_clean()
            resultado = super().save(*args, **kwargs)

            if self.estado != self.Estado.CANCELADO and self.kilometraje is not None:
                Moto.objects.filter(pk=moto.pk).filter(
                    Q(kilometraje_actual__isnull=True)
                    | Q(kilometraje_actual__lt=self.kilometraje)
                ).update(
                    kilometraje_actual=self.kilometraje,
                    actualizado_en=timezone.now(),
                )

            return resultado

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y} — {self.moto}"
