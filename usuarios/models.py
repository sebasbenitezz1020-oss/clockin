from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = "admin", "Administrador"
        RRHH = "rrhh", "RRHH"
        SUPERVISOR = "supervisor", "Supervisor"
        OPERADOR = "operador", "Operador"
        FUNCIONARIO = "funcionario", "Funcionario"

    rol = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.OPERADOR
    )
    telefono = models.CharField(max_length=30, blank=True, null=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_rol_display()})"