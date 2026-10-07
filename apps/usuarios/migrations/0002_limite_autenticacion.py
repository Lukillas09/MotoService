from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0001_email_normalizado_unico"),
    ]

    operations = [
        migrations.CreateModel(
            name="LimiteAutenticacion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "ambito",
                    models.CharField(
                        choices=[
                            ("LOGIN_IP", "Login por IP"),
                            ("LOGIN_IDENTIFICADOR", "Login por identificador"),
                            ("PASSWORD_RESET_IP", "Recuperación por IP"),
                            ("PASSWORD_RESET_EMAIL", "Recuperación por email"),
                        ],
                        max_length=32,
                    ),
                ),
                ("sujeto_hash", models.CharField(max_length=64)),
                ("ventana_iniciada_en", models.DateTimeField()),
                ("intentos", models.PositiveIntegerField(default=0)),
                ("expira_en", models.DateTimeField()),
            ],
            options={
                "verbose_name": "límite de autenticación",
                "verbose_name_plural": "límites de autenticación",
                "indexes": [
                    models.Index(
                        fields=["expira_en"],
                        name="usuarios_limite_exp_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("ambito", "sujeto_hash"),
                        name="usuarios_limite_auth_uniq",
                    )
                ],
            },
        ),
    ]
