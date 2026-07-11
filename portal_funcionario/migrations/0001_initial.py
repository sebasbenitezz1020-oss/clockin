from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0040_empresa_icl_activo"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalDocumentoLectura",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("leido", models.BooleanField(default=False)),
                ("leido_en", models.DateTimeField(blank=True, null=True)),
                ("confirmado", models.BooleanField(default=False)),
                ("confirmado_en", models.DateTimeField(blank=True, null=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("documento", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="portal_lecturas", to="core.documentofuncionario")),
                ("empresa", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="portal_documentos_lectura", to="core.empresa")),
                ("funcionario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="portal_documentos_lectura", to="core.funcionario")),
                ("usuario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="portal_documentos_leidos", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-actualizado_en"],
                "unique_together": {("funcionario", "documento")},
            },
        ),
        migrations.CreateModel(
            name="PortalComunicacionLectura",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("abierto", models.BooleanField(default=False)),
                ("abierto_en", models.DateTimeField(blank=True, null=True)),
                ("confirmado", models.BooleanField(default=False)),
                ("confirmado_en", models.DateTimeField(blank=True, null=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("comunicacion", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="portal_lecturas", to="core.comunicacionlaboral")),
                ("empresa", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="portal_comunicaciones_lectura", to="core.empresa")),
                ("funcionario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="portal_comunicaciones_lectura", to="core.funcionario")),
                ("usuario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="portal_comunicaciones_leidas", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-actualizado_en"],
                "unique_together": {("funcionario", "comunicacion")},
            },
        ),
    ]
