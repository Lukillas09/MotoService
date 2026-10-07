import re

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.clientes.models import (
    Cliente,
    expresion_telefono_normalizado,
    normalizar_espacios,
    normalizar_telefono_busqueda,
)


def normalizar_patente(valor):
    patente = re.sub(r"[\s-]+", "", valor or "").upper()
    return patente or None


def validar_anio(valor):
    anio_maximo = timezone.localdate().year + 1
    if valor < 1900 or valor > anio_maximo:
        raise ValidationError(
            f"Ingresá un año entre 1900 y {anio_maximo}.",
            code="anio_fuera_de_rango",
        )


class MotoQuerySet(models.QuerySet):
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
                Q(marca__icontains=parte)
                | Q(modelo__icontains=parte)
                | Q(cliente__nombre__icontains=parte)
                | Q(cliente__apellido__icontains=parte)
                | Q(cliente__telefono__icontains=parte)
            )
            patente = normalizar_patente(parte)
            if patente:
                filtro_parte |= Q(patente__icontains=patente)
            if any(caracter.isdigit() for caracter in parte):
                telefono = normalizar_telefono_busqueda(parte)
                if telefono:
                    filtro_parte |= Q(
                        telefono_cliente_busqueda__icontains=telefono
                    )
            filtros &= filtro_parte

        return queryset.filter(filtros)


class Moto(models.Model):
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="motos",
        verbose_name="cliente",
    )
    patente = models.CharField(
        "patente",
        max_length=20,
        blank=True,
        null=True,
        unique=True,
    )
    marca = models.CharField("marca", max_length=80)
    modelo = models.CharField("modelo", max_length=100)
    anio = models.PositiveSmallIntegerField(
        "año",
        blank=True,
        null=True,
        validators=(validar_anio,),
    )
    cilindrada_cc = models.PositiveIntegerField(
        "cilindrada",
        blank=True,
        null=True,
        validators=(MinValueValidator(0),),
    )
    color = models.CharField("color", max_length=50, blank=True)
    kilometraje_actual = models.PositiveIntegerField(
        "último kilometraje registrado",
        blank=True,
        null=True,
        validators=(MinValueValidator(0),),
    )
    numero_chasis = models.CharField("número de chasis", max_length=100, blank=True)
    numero_motor = models.CharField("número de motor", max_length=100, blank=True)
    observaciones = models.TextField("observaciones", blank=True)
    activo = models.BooleanField("activa", default=True)
    creado_en = models.DateTimeField("creada el", auto_now_add=True)
    actualizado_en = models.DateTimeField("actualizada el", auto_now=True)

    objects = MotoQuerySet.as_manager()

    class Meta:
        ordering = ("marca", "modelo", "pk")
        verbose_name = "moto"
        verbose_name_plural = "motos"

    def clean(self):
        super().clean()
        marca_original = self.marca
        modelo_original = self.modelo
        self.patente = normalizar_patente(self.patente)
        self.marca = normalizar_espacios(self.marca)
        self.modelo = normalizar_espacios(self.modelo)
        self.color = normalizar_espacios(self.color)
        self.numero_chasis = (self.numero_chasis or "").strip()
        self.numero_motor = (self.numero_motor or "").strip()

        errores = {}
        if marca_original and not self.marca:
            errores["marca"] = "Ingresá la marca de la moto."
        if modelo_original and not self.modelo:
            errores["modelo"] = "Ingresá el modelo de la moto."
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        actualiza_kilometraje = (
            update_fields is None or "kilometraje_actual" in update_fields
        )

        with transaction.atomic():
            if self._state.adding:
                if self.cliente_id:
                    try:
                        cliente = Cliente.objects.select_for_update(no_key=True).get(
                            pk=self.cliente_id
                        )
                    except Cliente.DoesNotExist as error:
                        raise ValidationError(
                            {"cliente": "El cliente seleccionado no existe."}
                        ) from error
                    if not cliente.activo:
                        raise ValidationError(
                            {
                                "cliente": (
                                    "Restaurá el cliente antes de registrar una moto nueva."
                                )
                            }
                        )
            elif actualiza_kilometraje:
                actual = (
                    type(self)
                    .objects.select_for_update(no_key=True)
                    .only("kilometraje_actual")
                    .get(pk=self.pk)
                )
                if actual.kilometraje_actual is not None and (
                    self.kilometraje_actual is None
                    or self.kilometraje_actual < actual.kilometraje_actual
                ):
                    actual_formateado = f"{actual.kilometraje_actual:,}".replace(
                        ",", "."
                    )
                    raise ValidationError(
                        {
                            "kilometraje_actual": (
                                "El kilometraje no puede ser menor al último registrado "
                                f"({actual_formateado} km). Verificá el valor ingresado."
                            )
                        }
                    )

            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        descripcion = f"{self.marca} {self.modelo}"
        if self.patente:
            return f"{descripcion} — {self.patente}"
        return descripcion
