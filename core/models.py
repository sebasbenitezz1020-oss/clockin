from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta


class Empresa(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    ruc = models.CharField(max_length=30, blank=True, default="")
    activo = models.BooleanField(default=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Sucursal(models.Model):
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="sucursales"
    )
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=255, blank=True, default="")
    activo = models.BooleanField(default=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["empresa__nombre", "nombre"]
        unique_together = ("empresa", "nombre")

    def __str__(self):
        return f"{self.empresa.nombre} - {self.nombre}"


class Turno(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    hora_entrada = models.TimeField()
    hora_salida = models.TimeField()

    usa_almuerzo = models.BooleanField(default=False)
    hora_inicio_almuerzo = models.TimeField(null=True, blank=True)
    hora_fin_almuerzo = models.TimeField(null=True, blank=True)

    tolerancia_minutos = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Funcionario(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    cedula = models.CharField(max_length=30, unique=True)

    face_encoding = models.BinaryField(null=True, blank=True)

    turno = models.ForeignKey(
        Turno,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="funcionarios"
    )
    cargo = models.CharField(max_length=100, blank=True, default="")
    sector = models.CharField(max_length=100, blank=True, default="")

    # Campo viejo legado (se mantiene para no romper nada)
    sucursal = models.CharField(max_length=100, blank=True, default="")

    # Nueva relación real
    sucursal_rel = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="funcionarios"
    )

    ips = models.BooleanField(default=False)
    salario_base = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bono = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    fecha_ingreso = models.DateField(null=True, blank=True)
    foto = models.ImageField(upload_to="funcionarios/", null=True, blank=True)

    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["apellido", "nombre"]

    def __str__(self):
        return f"{self.apellido}, {self.nombre} - CI: {self.cedula}"

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"

    @property
    def empresa(self):
        if self.sucursal_rel and self.sucursal_rel.empresa:
            return self.sucursal_rel.empresa
        return None

    @property
    def empresa_mostrar(self):
        if self.empresa:
            return self.empresa.nombre
        return "-"

    @property
    def sucursal_mostrar(self):
        if self.sucursal_rel:
            return self.sucursal_rel.nombre
        return self.sucursal or "-"

    @property
    def antiguedad_anios(self):
        if not self.fecha_ingreso:
            return 0
        hoy = timezone.localdate()
        anios = hoy.year - self.fecha_ingreso.year
        if (hoy.month, hoy.day) < (self.fecha_ingreso.month, self.fecha_ingreso.day):
            anios -= 1
        return max(anios, 0)

    @property
    def dias_vacaciones_corresponden(self):
        anios = self.antiguedad_anios
        if anios < 5:
            return 12
        elif anios < 10:
            return 18
        return 30

    @property
    def dias_vacaciones_usados(self):
        total = self.vacaciones.filter(
            estado=Vacacion.Estados.APROBADO
        ).aggregate(total=models.Sum("dias_solicitados"))["total"]
        return total or 0

    @property
    def saldo_vacaciones(self):
        return max(self.dias_vacaciones_corresponden - self.dias_vacaciones_usados, 0)


class Asistencia(models.Model):
    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="asistencias"
    )
    fecha = models.DateField(default=timezone.localdate)

    hora_entrada = models.DateTimeField(null=True, blank=True)
    hora_salida = models.DateTimeField(null=True, blank=True)

    minutos_atraso = models.PositiveIntegerField(default=0)
    llego_tarde = models.BooleanField(default=False)

    observacion = models.CharField(max_length=255, blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha", "-hora_entrada"]
        unique_together = ("funcionario", "fecha")

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.fecha}"

    def calcular_atraso(self):
        if not self.hora_entrada or not self.funcionario.turno:
            self.minutos_atraso = 0
            self.llego_tarde = False
            return

        turno = self.funcionario.turno
        entrada_programada = timezone.make_aware(
            datetime.combine(self.fecha, turno.hora_entrada)
        )
        entrada_con_tolerancia = entrada_programada + timedelta(minutes=turno.tolerancia_minutos)

        if self.hora_entrada > entrada_con_tolerancia:
            diferencia = self.hora_entrada - entrada_programada
            self.minutos_atraso = max(0, int(diferencia.total_seconds() // 60))
            self.llego_tarde = True
        else:
            self.minutos_atraso = 0
            self.llego_tarde = False


class PermisoLicencia(models.Model):
    class Tipos(models.TextChoices):
        PERMISO_PERSONAL = "permiso_personal", "Permiso personal"
        REPOSO_MEDICO = "reposo_medico", "Reposo médico"
        VACACION_PROVISIONAL = "vacacion_provisional", "Vacación provisional"
        LICENCIA_ESPECIAL = "licencia_especial", "Licencia especial"
        OTRO = "otro", "Otro"

    class Estados(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        APROBADO = "aprobado", "Aprobado"
        RECHAZADO = "rechazado", "Rechazado"
        ANULADO = "anulado", "Anulado"

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="permisos_licencias"
    )
    tipo = models.CharField(max_length=40, choices=Tipos.choices, default=Tipos.PERMISO_PERSONAL)
    fecha_desde = models.DateField()
    fecha_hasta = models.DateField()
    motivo = models.TextField(blank=True, default="")
    adjunto = models.FileField(upload_to="permisos/", null=True, blank=True)

    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.PENDIENTE)
    observacion = models.TextField(blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_desde", "-creado_en"]

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.get_tipo_display()} ({self.fecha_desde} a {self.fecha_hasta})"

    @property
    def dias(self):
        return (self.fecha_hasta - self.fecha_desde).days + 1


class Vacacion(models.Model):
    class Estados(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        APROBADO = "aprobado", "Aprobado"
        RECHAZADO = "rechazado", "Rechazado"
        ANULADO = "anulado", "Anulado"

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="vacaciones"
    )
    fecha_desde = models.DateField()
    fecha_hasta = models.DateField()
    dias_solicitados = models.PositiveIntegerField(default=1)
    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.PENDIENTE)
    observacion = models.TextField(blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_desde", "-creado_en"]

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - Vacaciones ({self.fecha_desde} a {self.fecha_hasta})"


class HistorialAccion(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acciones_historial"
    )
    modulo = models.CharField(max_length=50)
    accion = models.CharField(max_length=50)
    descripcion = models.TextField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.modulo} - {self.accion} - {self.creado_en:%d/%m/%Y %H:%M}"