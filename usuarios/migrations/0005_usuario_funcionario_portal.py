from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0040_empresa_icl_activo"),
        ("usuarios", "0004_alter_permisousuario_modulo"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="funcionario",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="usuario_portal",
                to="core.funcionario",
            ),
        ),
        migrations.AddField(
            model_name="usuario",
            name="portal_activo",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="usuario",
            name="requiere_cambio_password",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="permisousuario",
            name="modulo",
            field=models.CharField(
                choices=[
                    ("dashboard", "Dashboard"),
                    ("empresas", "Empresas"),
                    ("sucursales", "Sucursales"),
                    ("funcionarios", "Funcionarios"),
                    ("portal_funcionario", "Portal del Funcionario"),
                    ("usuarios", "Usuarios y Permisos"),
                    ("turnos", "Turnos"),
                    ("dias_libres", "Días Libres"),
                    ("asistencia", "Asistencia"),
                    ("biometrico", "Biométrico"),
                    ("banco_horas", "Banco de Horas"),
                    ("permisos", "Permisos / Licencias"),
                    ("vacaciones", "Vacaciones"),
                    ("comunicaciones", "Comunicaciones"),
                    ("deudas", "Deudas"),
                    ("nomina", "Nómina"),
                    ("aguinaldo", "Aguinaldo"),
                    ("planilla_bancaria", "Planilla Bancaria"),
                    ("liquidacion", "Liquidación"),
                    ("icl", "ICL"),
                    ("reportes", "Reportes"),
                    ("historial", "Historial"),
                    ("configuracion", "Configuración"),
                ],
                max_length=50,
            ),
        ),
    ]
