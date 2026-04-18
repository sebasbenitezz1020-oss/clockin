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


class PermisoUsuario(models.Model):
    class Modulos(models.TextChoices):
        DASHBOARD = "dashboard", "Dashboard"
        EMPRESAS = "empresas", "Empresas"
        SUCURSALES = "sucursales", "Sucursales"
        FUNCIONARIOS = "funcionarios", "Funcionarios"
        TURNOS = "turnos", "Turnos"
        ASISTENCIA = "asistencia", "Asistencia"
        DIAS_LIBRES = "dias_libres", "Días Libres"
        DEUDAS = "deudas", "Deudas"
        NOMINA = "nomina", "Nómina"
        BIOMETRICO = "biometrico", "Biométrico"
        PERMISOS = "permisos", "Permisos / Licencias"
        VACACIONES = "vacaciones", "Vacaciones"
        ICL = "icl", "ICL"
        REPORTES = "reportes", "Reportes"
        HISTORIAL = "historial", "Historial"
        LIQUIDACION = "liquidacion", "Liquidación"
        CONFIGURACION = "configuracion", "Configuración"

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="permisos_personalizados"
    )

    modulo = models.CharField(
        max_length=50,
        choices=Modulos.choices
    )

    puede_ver = models.BooleanField(default=False)
    puede_crear = models.BooleanField(default=False)
    puede_editar = models.BooleanField(default=False)
    puede_eliminar = models.BooleanField(default=False)

    puede_aprobar = models.BooleanField(default=False)
    puede_confirmar = models.BooleanField(default=False)
    puede_pagar = models.BooleanField(default=False)
    puede_anular = models.BooleanField(default=False)

    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Permiso de usuario"
        verbose_name_plural = "Permisos de usuarios"
        unique_together = ("usuario", "modulo")
        ordering = ["usuario", "modulo"]

    def __str__(self):
        return f"{self.usuario.username} - {self.get_modulo_display()}"