from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0039_historialaccion_empresa"),
    ]

    operations = [
        migrations.AddField(
            model_name="empresa",
            name="icl_activo",
            field=models.BooleanField(default=True),
        ),
    ]
