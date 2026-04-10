from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal


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
    class ModalidadesCobro(models.TextChoices):
        TRANSFERENCIA = "transferencia", "Transferencia bancaria"
        EFECTIVO = "efectivo", "Cobrar en efectivo"

    class Bancos(models.TextChoices):
        NINGUNO = "", "---------"
        ITAU = "itau", "Itaú"
        CONTINENTAL = "continental", "Continental"
        SUDAMERIS = "sudameris", "Sudameris"
        BASA = "basa", "Basa"
        GNB = "gnb", "GNB"
        FAMILIAR = "familiar", "Familiar"
        UENO = "ueno", "Ueno"
        VISION = "vision", "Visión"
        ATLAS = "atlas", "Atlas"
        RIO = "rio", "Banco Río"
        OTRO = "otro", "Otro"

    class TiposCuenta(models.TextChoices):
        NINGUNO = "", "---------"
        AHORRO = "ahorro", "Caja de ahorro"
        CORRIENTE = "corriente", "Cuenta corriente"

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
    sucursal = models.CharField(max_length=100, blank=True, default="")
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

    porcentaje_limite_deuda = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=30.00,
        help_text="Porcentaje máximo recomendado de deuda sobre salario base."
    )

    modalidad_cobro = models.CharField(
        max_length=20,
        choices=ModalidadesCobro.choices,
        default=ModalidadesCobro.TRANSFERENCIA
    )
    banco = models.CharField(
        max_length=30,
        choices=Bancos.choices,
        blank=True,
        default=""
    )
    tipo_cuenta = models.CharField(
        max_length=20,
        choices=TiposCuenta.choices,
        blank=True,
        default=""
    )
    numero_cuenta = models.CharField(max_length=50, blank=True, default="")

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

    @property
    def salario_bruto(self):
        """
        Salario bruto teórico sin aplicar ICL.
        Se mantiene para referencia general.
        En nómina mensual debe usarse el salario_bruto calculado del período.
        """
        return (Decimal(self.salario_base or 0) + Decimal(self.bono or 0)).quantize(Decimal("0.01"))

    @property
    def descuento_ips(self):
        if self.ips:
            return (Decimal(self.salario_base or 0) * Decimal("0.09")).quantize(Decimal("0.01"))
        return Decimal("0.00")

    @property
    def total_deuda_activa(self):
        total = self.deudas.filter(activa=True).aggregate(
            total=models.Sum("saldo_pendiente")
        )["total"]
        return total or Decimal("0.00")

    @property
    def descuento_deudas_mes(self):
        total = Decimal("0.00")
        for deuda in self.deudas.filter(activa=True, aplicar_en_nomina=True):
            total += deuda.descuento_mes
        return total.quantize(Decimal("0.01"))

    @property
    def limite_deuda_monto(self):
        return (
            Decimal(self.salario_base or 0) * (Decimal(self.porcentaje_limite_deuda or 0) / Decimal("100"))
        ).quantize(Decimal("0.01"))

    @property
    def disponible_deuda(self):
        disponible = self.limite_deuda_monto - self.total_deuda_activa
        if disponible < 0:
            return Decimal("0.00")
        return disponible.quantize(Decimal("0.01"))

    @property
    def excede_limite_deuda(self):
        return self.total_deuda_activa > self.limite_deuda_monto

    @property
    def salario_neto_estimado(self):
        neto = self.salario_bruto - self.descuento_ips - self.descuento_deudas_mes
        if neto < 0:
            return Decimal("0.00")
        return neto.quantize(Decimal("0.01"))


class Asistencia(models.Model):
    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="asistencias"
    )
    fecha = models.DateField(default=timezone.localdate)

    hora_entrada = models.DateTimeField(null=True, blank=True)
    hora_salida_almuerzo = models.DateTimeField(null=True, blank=True)
    hora_regreso_almuerzo = models.DateTimeField(null=True, blank=True)
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

    @property
    def siguiente_marcacion(self):
        if not self.hora_entrada:
            return "entrada"

        if self.funcionario.turno and self.funcionario.turno.usa_almuerzo:
            if not self.hora_salida_almuerzo:
                return "salida_almuerzo"
            if not self.hora_regreso_almuerzo:
                return "regreso_almuerzo"

        if not self.hora_salida:
            return "salida"

        return "completo"

    @property
    def horas_trabajadas_segundos(self):
        total = 0

        if self.hora_entrada:
            if self.funcionario.turno and self.funcionario.turno.usa_almuerzo:
                if self.hora_salida_almuerzo:
                    total += int((self.hora_salida_almuerzo - self.hora_entrada).total_seconds())

                if self.hora_regreso_almuerzo and self.hora_salida:
                    total += int((self.hora_salida - self.hora_regreso_almuerzo).total_seconds())
                elif self.hora_regreso_almuerzo and not self.hora_salida:
                    ahora = timezone.localtime()
                    total += int((ahora - self.hora_regreso_almuerzo).total_seconds())
            else:
                if self.hora_salida:
                    total += int((self.hora_salida - self.hora_entrada).total_seconds())
                else:
                    ahora = timezone.localtime()
                    total += int((ahora - self.hora_entrada).total_seconds())

        return max(total, 0)

    @property
    def horas_trabajadas_texto(self):
        segundos = self.horas_trabajadas_segundos
        horas = segundos // 3600
        minutos = (segundos % 3600) // 60
        return f"{horas:02d}:{minutos:02d}"

    @property
    def estado_jornada(self):
        if not self.hora_entrada:
            return "Pendiente"

        if self.funcionario.turno and self.funcionario.turno.usa_almuerzo:
            if not self.hora_salida_almuerzo:
                return "Trabajando"
            if not self.hora_regreso_almuerzo:
                return "En almuerzo"
            if not self.hora_salida:
                return "Trabajando"
            return "Finalizado"

        if not self.hora_salida:
            return "Trabajando"

        return "Finalizado"


class Deuda(models.Model):
    class Tipos(models.TextChoices):
        VALE_COMPRA = "vale_compra", "Vale compra"
        PRESTAMO = "prestamo", "Préstamo"
        ADELANTO = "adelanto", "Adelanto"
        OTRO = "otro", "Otro"

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="deudas"
    )
    tipo = models.CharField(max_length=30, choices=Tipos.choices, default=Tipos.VALE_COMPRA)
    descripcion = models.CharField(max_length=255, blank=True, default="")
    fecha = models.DateField(default=timezone.localdate)

    monto_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    saldo_pendiente = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cuota_mensual = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    aplicar_en_nomina = models.BooleanField(default=True)
    activa = models.BooleanField(default=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha", "-creado_en"]

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.get_tipo_display()} - {self.saldo_pendiente}"

    def save(self, *args, **kwargs):
        if self.saldo_pendiente is None or self.saldo_pendiente == Decimal("0"):
            self.saldo_pendiente = self.monto_total or Decimal("0.00")

        if self.saldo_pendiente <= 0:
            self.saldo_pendiente = Decimal("0.00")
            self.activa = False

        super().save(*args, **kwargs)

    @property
    def descuento_mes(self):
        if not self.aplicar_en_nomina or not self.activa:
            return Decimal("0.00")
        cuota = Decimal(self.cuota_mensual or 0)
        saldo = Decimal(self.saldo_pendiente or 0)
        if cuota <= 0:
            return saldo.quantize(Decimal("0.01"))
        return min(cuota, saldo).quantize(Decimal("0.01"))

    @property
    def porcentaje_sobre_salario(self):
        salario = Decimal(self.funcionario.salario_base or 0)
        if salario <= 0:
            return Decimal("0.00")
        return ((Decimal(self.saldo_pendiente or 0) / salario) * Decimal("100")).quantize(Decimal("0.01"))


class NominaMensual(models.Model):
    class EstadosPago(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PAGADO = "pagado", "Pagado"
        ANULADO = "anulado", "Anulado"

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="nominas"
    )
    mes = models.PositiveSmallIntegerField()
    anio = models.PositiveIntegerField()

    salario_base = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bono_base = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bono_icl = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    salario_bruto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    descuento_ips = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    descuento_deudas = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    salario_neto = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    modalidad_cobro = models.CharField(max_length=20, blank=True, default="")
    banco = models.CharField(max_length=30, blank=True, default="")
    tipo_cuenta = models.CharField(max_length=20, blank=True, default="")
    numero_cuenta = models.CharField(max_length=50, blank=True, default="")

    estado_pago = models.CharField(
        max_length=20,
        choices=EstadosPago.choices,
        default=EstadosPago.PENDIENTE
    )
    fecha_pago = models.DateField(null=True, blank=True)
    observacion = models.TextField(blank=True, default="")
    extracto_firmado = models.FileField(upload_to="nomina/extractos_firmados/", null=True, blank=True)
    comprobante_pago = models.FileField(upload_to="nomina/comprobantes/", null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-anio", "-mes", "funcionario__apellido", "funcionario__nombre"]
        unique_together = ("funcionario", "mes", "anio")

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - Nómina {self.mes:02d}/{self.anio}"


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