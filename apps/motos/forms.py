from django import forms
from django.db.models import Q

from apps.clientes.models import Cliente
from apps.core.forms import BootstrapFormMixin

from .models import Moto


class MotoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Moto
        fields = (
            "cliente",
            "patente",
            "marca",
            "modelo",
            "anio",
            "cilindrada_cc",
            "color",
            "kilometraje_actual",
            "numero_chasis",
            "numero_motor",
            "observaciones",
        )
        labels = {
            "cliente": "Propietario",
            "cilindrada_cc": "Cilindrada (cc)",
            "kilometraje_actual": "Último kilometraje registrado",
        }
        help_texts = {
            "patente": "Opcional. Se guardará sin espacios ni guiones.",
            "kilometraje_actual": "Último valor conocido por el taller.",
        }
        widgets = {
            "patente": forms.TextInput(
                attrs={"autocomplete": "off", "placeholder": "AF123XY"}
            ),
            "anio": forms.NumberInput(attrs={"inputmode": "numeric"}),
            "cilindrada_cc": forms.NumberInput(attrs={"inputmode": "numeric"}),
            "kilometraje_actual": forms.NumberInput(
                attrs={"inputmode": "numeric"}
            ),
            "observaciones": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._kilometraje_actual_original = (
            self.instance.kilometraje_actual if self.instance.pk else None
        )
        clientes = Cliente.objects.filter(activo=True)
        if self.instance.pk and self.instance.cliente_id:
            clientes = Cliente.objects.filter(
                Q(activo=True) | Q(pk=self.instance.cliente_id)
            )
        self.fields["cliente"].queryset = clientes.order_by(
            "apellido", "nombre", "pk"
        )
        self.fields["cliente"].empty_label = "Seleccioná un cliente"

    def clean_kilometraje_actual(self):
        kilometraje = self.cleaned_data.get("kilometraje_actual")
        original = self._kilometraje_actual_original
        if original is not None and (kilometraje is None or kilometraje < original):
            original_formateado = f"{original:,}".replace(",", ".")
            raise forms.ValidationError(
                "El kilometraje no puede ser menor al último registrado "
                f"({original_formateado} km). Verificá el valor ingresado."
            )
        return kilometraje
