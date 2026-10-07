from django.db import models


class LimiteAutenticacion(models.Model):
    class Ambito(models.TextChoices):
        LOGIN_IP = "LOGIN_IP", "Login por IP"
        LOGIN_IDENTIFICADOR = "LOGIN_IDENTIFICADOR", "Login por identificador"
        PASSWORD_RESET_IP = "PASSWORD_RESET_IP", "Recuperación por IP"
        PASSWORD_RESET_EMAIL = "PASSWORD_RESET_EMAIL", "Recuperación por email"

    ambito = models.CharField(max_length=32, choices=Ambito.choices)
    sujeto_hash = models.CharField(max_length=64)
    ventana_iniciada_en = models.DateTimeField()
    intentos = models.PositiveIntegerField(default=0)
    expira_en = models.DateTimeField()

    class Meta:
        verbose_name = "límite de autenticación"
        verbose_name_plural = "límites de autenticación"
        constraints = [
            models.UniqueConstraint(
                fields=("ambito", "sujeto_hash"),
                name="usuarios_limite_auth_uniq",
            )
        ]
        indexes = [
            models.Index(
                fields=("expira_en",),
                name="usuarios_limite_exp_idx",
            )
        ]
