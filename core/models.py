from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from calendar import monthrange


class Empresa(models.Model):
    class Estados(models.TextChoices):
        ACTIVA = "activa", "Activa"
        SUSPENDIDA = "suspendida", "Suspendida"

    class Planes(models.TextChoices):
        BASICO = "basico", "Basico"
        PROFESIONAL = "profesional", "Profesional"
        EMPRESARIAL = "empresarial", "Empresarial"

    nombre = models.CharField(max_length=150, unique=True)
    nombre_comercial = models.CharField(max_length=150, blank=True, default="")
    razon_social = models.CharField(max_length=180, blank=True, default="")
    ruc = models.CharField(max_length=30, blank=True, default="")
    direccion = models.CharField(max_length=255, blank=True, default="")
    telefono = models.CharField(max_length=50, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    logo = models.ImageField(upload_to="empresas/logos/", null=True, blank=True)
    color_primario = models.CharField(max_length=20, blank=True, default="")
    color_secundario = models.CharField(max_length=20, blank=True, default="")
    tema_visual = models.CharField(max_length=20, blank=True, default="")
    texto_legal_pdf = models.TextField(blank=True, default="")
    icl_activo = models.BooleanField(default=True)
    permite_ajuste_manual_liquidacion = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.ACTIVA)
    plan_contratado = models.CharField(max_length=30, choices=Planes.choices, default=Planes.PROFESIONAL)
    fecha_vencimiento_suscripcion = models.DateField(null=True, blank=True)
    firma_gerente = models.ImageField(
        upload_to="empresas/firmas/",
        null=True,
        blank=True
    )

    nombre_gerente = models.CharField(
        max_length=150,
        blank=True,
        default=""
    )

    cargo_gerente = models.CharField(
        max_length=150,
        blank=True,
        default="Gerente General"
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @property
    def nombre_visible(self):
        return self.nombre_comercial or self.nombre

    @property
    def suscripcion_vencida(self):
        return bool(
            self.fecha_vencimiento_suscripcion
            and self.fecha_vencimiento_suscripcion < timezone.localdate()
        )

    @property
    def suscripcion_por_vencer(self):
        if not self.fecha_vencimiento_suscripcion:
            return False
        dias = (self.fecha_vencimiento_suscripcion - timezone.localdate()).days
        return 0 <= dias <= 7


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


class ConfiguracionGeneral(models.Model):
    TEMA_AZUL = "azul"
    TEMA_VERDE = "verde"
    TEMA_ROJO = "rojo"
    TEMA_NARANJA = "naranja"
    TEMA_MORADO = "morado"
    TEMA_TURQUESA = "turquesa"
    TEMA_GRIS = "gris"

    TEMAS_CHOICES = [
        (TEMA_AZUL, "Azul corporativo"),
        (TEMA_VERDE, "Verde premium"),
        (TEMA_ROJO, "Rojo ejecutivo"),
        (TEMA_NARANJA, "Naranja energético"),
        (TEMA_MORADO, "Morado moderno"),
        (TEMA_TURQUESA, "Turquesa tecnológico"),
        (TEMA_GRIS, "Gris oscuro elegante"),
    ]

    salario_base_default = models.DecimalField(max_digits=12, decimal_places=2, default=2899048)
    porcentaje_limite_deuda_default = models.DecimalField(max_digits=5, decimal_places=2, default=30.00)
    tolerancia_minutos_default = models.PositiveIntegerField(default=1)

    observacion_general = models.TextField(blank=True, default="")

    nombre_sistema = models.CharField(max_length=100, default="ClockIn")
    subtitulo_sistema = models.CharField(max_length=150, default="Sistema Web")
    color_primario = models.CharField(max_length=20, default=TEMA_AZUL)
    logo_url = models.URLField(blank=True, default="")

    bancos_personalizados = models.TextField(
        blank=True,
        default=(
            "Itaú\n"
            "Continental\n"
            "Sudameris\n"
            "Basa\n"
            "GNB\n"
            "Familiar\n"
            "Ueno\n"
            "Visión\n"
            "Atlas\n"
            "Banco Río\n"
            "Otro"
        )
    )

    cargos_personalizados = models.TextField(
        blank=True,
        default=(
            "Cajera/o\n"
            "Encargado/a\n"
            "Marketing\n"
            "Digitación\n"
            "Cierre de Compras\n"
            "Compras\n"
            "Tesorería\n"
            "Pagos\n"
            "RRHH\n"
            "Contabilidad\n"
            "Financiero\n"
            "Repositor/a\n"
            "Recepcionista\n"
            "Balconista\n"
            "Carnicero\n"
            "Auxiliar\n"
            "Auxiliar RRHH\n"
            "Delivery\n"
            "Pizzero\n"
            "Chapero\n"
            "Ayudante\n"
            "Limpiadora\n"
            "Mozo\n"
            "Bartender\n"
            "Churrasquero\n"
            "Pasador\n"
            "Panadero/a\n"
            "Confitero/a\n"
            "Saladero/a\n"
            "Buffet\n"
            "Cocinera\n"
            "Ayudante de Cocina\n"
            "Depositero\n"
            "Recepcionista de Mercaderías\n"
            "Gerente\n"
            "Informático\n"
            "Técnico de Mantenimiento\n"
            "Inventario\n"
            "Logistica"

        )
    )

    sectores_personalizados = models.TextField(
        blank=True,
        default=(
            "Administración\n"
            "RRHH\n"
            "Panadería\n"
            "Financiero\n"
            "Caja\n"
            "Salón\n"
            "Carnicería\n"
            "Hortifrut\n"
            "Depósito\n"
            "Recepción\n"
            "Mantenimiento\n"
            "Limpieza\n"
            "Cocina\n"
            "Copa\n"
            "Fríos\n"
            "Churrasquería"
        )
    )

    biometrico_segundos_lectura = models.PositiveIntegerField(default=1)
    biometrico_pausa_exito_ms = models.PositiveIntegerField(default=4000)
    biometrico_pausa_aviso_ms = models.PositiveIntegerField(default=3000)
    biometrico_pausa_error_ms = models.PositiveIntegerField(default=2200)
    biometrico_sonidos_activos = models.BooleanField(default=True)
    biometrico_fullscreen_auto = models.BooleanField(default=True)

    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración general"
        verbose_name_plural = "Configuraciones generales"

    def __str__(self):
        return "Configuración general ClockIn"

    @classmethod
    def obtener(cls):
        obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                "salario_base_default": Decimal("2899048.00"),
                "porcentaje_limite_deuda_default": Decimal("30.00"),
                "tolerancia_minutos_default": 1,
                "observacion_general": "",
                "nombre_sistema": "ClockIn",
                "subtitulo_sistema": "Sistema Web",
                "color_primario": cls.TEMA_AZUL,
                "logo_url": "",
                "bancos_personalizados": (
                    "Itaú\nContinental\nSudameris\nBasa\nGNB\nFamiliar\nUeno\nVisión\nAtlas\nBanco Río\nOtro"
                ),
                "cargos_personalizados": (
                    "Cajera/o\nEncargado/a\nMarketing\nDigitación\nCierre de Compras\nCompras\nTesorería\nPagos\n"
                    "RRHH\nContabilidad\nFinanciero\nRepositor/a\nRecepcionista\nBalconista\nCarnicero\nAuxiliar\n"
                    "Auxiliar RRHH\nDelivery\nPizzero\nChapero\nAyudante\nLimpiadora\nMozo\nBartender\n"
                    "Churrasquero\nPasador\nPanadero/a\nConfitero/a\nSaladero/a\nBuffet\nCocinera\n"
                    "Ayudante de Cocina\nDepositero\nRecepcionista de Mercaderías\nGerente\nInformático\n"
                    "Técnico de Mantenimiento"
                ),
                "sectores_personalizados": (
                    "Administración\nRRHH\nPanadería\nFinanciero\nCaja\nSalón\nCarnicería\nHortifrut\n"
                    "Depósito\nRecepción\nMantenimiento\nLimpieza\nCocina\nCopa\nChurrasquería"
                ),
                "biometrico_segundos_lectura": 1,
                "biometrico_pausa_exito_ms": 4000,
                "biometrico_pausa_aviso_ms": 3000,
                "biometrico_pausa_error_ms": 2200,
                "biometrico_sonidos_activos": True,
                "biometrico_fullscreen_auto": True,
            }
        )
        return obj

    def _parse_lista(self, texto):
        items = []
        for linea in (texto or "").splitlines():
            valor = linea.strip()
            if valor and valor not in items:
                items.append(valor)
        return items

    @property
    def bancos_lista(self):
        return self._parse_lista(self.bancos_personalizados)

    @property
    def cargos_lista(self):
        return self._parse_lista(self.cargos_personalizados)

    @property
    def sectores_lista(self):
        return self._parse_lista(self.sectores_personalizados)

    @property
    def bancos_choices(self):
        return [(item, item) for item in self.bancos_lista]

    @property
    def cargos_choices(self):
        return [(item, item) for item in self.cargos_lista]

    @property
    def sectores_choices(self):
        return [(item, item) for item in self.sectores_lista]

    @property
    def tema_nombre(self):
        mapa = dict(self.TEMAS_CHOICES)
        return mapa.get(self.color_primario, "Azul corporativo")


class Turno(models.Model):
    empresa = models.ForeignKey(
    "Empresa",
    on_delete=models.CASCADE,
    related_name="turnos",
    null=True,
    blank=True
)
    nombre = models.CharField(max_length=100)

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
        unique_together = ("empresa", "nombre")
        ordering = ["empresa__nombre", "nombre"]

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

    class Sectores(models.TextChoices):
        ADMINISTRACION = "Administración", "Administración"
        RRHH = "RRHH", "RRHH"
        PANADERIA = "Panadería", "Panadería"
        FINANCIERO = "Financiero", "Financiero"
        CAJA = "Caja", "Caja"
        SALON = "Salón", "Salón"
        CARNICERIA = "Carnicería", "Carnicería"
        HORTIFRUT = "Hortifrut", "Hortifrut"
        DEPOSITO = "Depósito", "Depósito"
        RECEPCION = "Recepción", "Recepción"
        MANTENIMIENTO = "Mantenimiento", "Mantenimiento"
        LIMPIEZA = "Limpieza", "Limpieza"
        COCINA = "Cocina", "Cocina"
        COPA = "Copa", "Copa"
        CHURRASQUERIA = "Churrasquería", "Churrasquería"

    class Cargos(models.TextChoices):
        CAJERA = "Cajera/o", "Cajera/o"
        ENCARGADO = "Encargado/a", "Encargado/a"
        MARKETING = "Marketing", "Marketing"
        DIGITACION = "Digitación", "Digitación"
        CIERRE_COMPRAS = "Cierre de Compras", "Cierre de Compras"
        COMPRAS = "Compras", "Compras"
        TESORERIA = "Tesorería", "Tesorería"
        PAGOS = "Pagos", "Pagos"
        RRHH = "RRHH", "RRHH"
        CONTABILIDAD = "Contabilidad", "Contabilidad"
        FINANCIERO = "Financiero", "Financiero"
        REPOSITOR = "Repositor/a", "Repositor/a"
        RECEPCIONISTA = "Recepcionista", "Recepcionista"
        BALCONISTA = "Balconista", "Balconista"
        CARNICERO = "Carnicero", "Carnicero"
        AUXILIAR = "Auxiliar", "Auxiliar"
        AUXILIAR_RRHH = "Auxiliar RRHH", "Auxiliar RRHH"
        DELIVERY = "Delivery", "Delivery"
        PIZZERO = "Pizzero", "Pizzero"
        CHAPERO = "Chapero", "Chapero"
        AYUDANTE = "Ayudante", "Ayudante"
        LIMPIADORA = "Limpiadora", "Limpiadora"
        MOZO = "Mozo", "Mozo"
        BARTENDER = "Bartender", "Bartender"
        CHURRASQUERO = "Churrasquero", "Churrasquero"
        PASADOR = "Pasador", "Pasador"
        PANADERO = "Panadero/a", "Panadero/a"
        CONFITERO = "Confitero/a", "Confitero/a"
        SALADERO = "Saladero/a", "Saladero/a"
        BUFFET = "Buffet", "Buffet"
        COCINERA = "Cocinera", "Cocinera"
        AYUDANTE_COCINA = "Ayudante de Cocina", "Ayudante de Cocina"
        DEPOSITERO = "Depositero", "Depositero"
        RECEPCIONISTA_MERCADERIAS = "Recepcionista de Mercaderías", "Recepcionista de Mercaderías"
        GERENTE = "Gerente", "Gerente"
        INFORMATICO = "Informático", "Informático"
        TECNICO_MANTENIMIENTO = "Técnico de Mantenimiento", "Técnico de Mantenimiento"

    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    cedula = models.CharField(max_length=30)
    tipo_documento = models.CharField(
        max_length=10,
        choices=[
            ("CI", "Cédula de Identidad"),
            ("CPF", "CPF"),
            ("CNPJ", "CNPJ"),
        ],
        default="CI",
    )

    face_encoding = models.BinaryField(null=True, blank=True)

    turno = models.ForeignKey(
        Turno,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="funcionarios"
    )
    cargo = models.CharField(max_length=100, choices=Cargos.choices, blank=True, default="")
    sector = models.CharField(max_length=100, choices=Sectores.choices, blank=True, default="")
    sucursal = models.CharField(max_length=100, blank=True, default="")
    sucursal_rel = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="funcionarios"
    )

    ips = models.BooleanField(default=False)
    salario_base = models.DecimalField(max_digits=12, decimal_places=2, default=2899048)
    bono = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    usa_salario_diferenciado = models.BooleanField(default=False)
    salario_diferenciado = models.DecimalField(max_digits=12, decimal_places=2, default=0)

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

    direccion = models.CharField(max_length=255, blank=True, default="")
    ciudad = models.CharField(max_length=120, blank=True, default="")
    departamento = models.CharField(max_length=120, blank=True, default="")
    telefono = models.CharField(max_length=50, blank=True, default="")
    correo = models.EmailField(blank=True, default="")
    fecha_nacimiento = models.DateField(null=True, blank=True)
    nacionalidad = models.CharField(max_length=100, blank=True, default="")
    estado_civil = models.CharField(max_length=80, blank=True, default="")

    contacto_emergencia_nombre = models.CharField(max_length=150, blank=True, default="")
    contacto_emergencia_parentesco = models.CharField(max_length=100, blank=True, default="")
    contacto_emergencia_telefono = models.CharField(max_length=50, blank=True, default="")

    tipo_sangre = models.CharField(max_length=20, blank=True, default="")
    alergias = models.TextField(blank=True, default="")
    enfermedad_importante = models.TextField(blank=True, default="")
    medicacion_actual = models.TextField(blank=True, default="")
    seguro_medico = models.CharField(max_length=150, blank=True, default="")

    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["apellido", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_documento", "cedula"],
                name="uniq_funcionario_tipo_documento_cedula",
            )
        ]

    def __str__(self):
        return f"{self.apellido}, {self.nombre} - {self.documento_compacto}"

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"

    @property
    def documento_numero(self):
        return self.cedula or ""

    @property
    def documento_formateado(self):
        valor = "".join(ch for ch in str(self.cedula or "") if ch.isdigit())
        if self.tipo_documento == "CPF" and len(valor) == 11:
            return f"{valor[:3]}.{valor[3:6]}.{valor[6:9]}-{valor[9:]}"
        if self.tipo_documento == "CNPJ" and len(valor) == 14:
            return f"{valor[:2]}.{valor[2:5]}.{valor[5:8]}/{valor[8:12]}-{valor[12:]}"
        if self.tipo_documento == "CI" and valor and valor == str(self.cedula or ""):
            return f"{int(valor):,}".replace(",", ".")
        return self.cedula or "-"

    @property
    def documento_etiqueta(self):
        return self.tipo_documento or "CI"

    @property
    def documento_compacto(self):
        return f"{self.documento_etiqueta}: {self.documento_formateado}"

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
        return self.salario_bruto_aplicable

    @property
    def neto_referencial(self):
        return self.salario_bruto_aplicable

    @property
    def modalidad_salarial(self):
        return "diferenciado" if self.usa_salario_diferenciado else "normal"

    @property
    def modalidad_salarial_display(self):
        return "Salario diferenciado" if self.usa_salario_diferenciado else "Salario base + bono"

    @property
    def salario_base_aplicable(self):
        if self.usa_salario_diferenciado:
            return Decimal(self.salario_diferenciado or 0).quantize(Decimal("0.01"))
        return Decimal(self.salario_base or 0).quantize(Decimal("0.01"))

    @property
    def bono_aplicable(self):
        if self.usa_salario_diferenciado:
            return Decimal("0.00")
        return Decimal(self.bono or 0).quantize(Decimal("0.01"))

    @property
    def salario_bruto_aplicable(self):
        if self.usa_salario_diferenciado:
            return Decimal(self.salario_diferenciado or 0).quantize(Decimal("0.01"))
        return (
            Decimal(self.salario_base or 0) + Decimal(self.bono or 0)
        ).quantize(Decimal("0.01"))

    @property
    def descuento_ips(self):
        if self.ips:
            return (self.salario_bruto_aplicable * Decimal("0.09")).quantize(Decimal("0.01"))
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
            self.salario_bruto_aplicable * (Decimal(self.porcentaje_limite_deuda or 0) / Decimal("100"))
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
    
class DocumentoFuncionario(models.Model):
    class Tipos(models.TextChoices):
        CEDULA_FRENTE = "cedula_frente", "Cédula frente"
        CEDULA_DORSO = "cedula_dorso", "Cédula dorso"
        CONTRATO = "contrato", "Contrato laboral"
        CURRICULUM = "curriculum", "Currículum"
        CERTIFICADO = "certificado", "Certificado"
        ANTECEDENTE = "antecedente", "Antecedente"
        MEDICO = "medico", "Documento médico"
        OTRO = "otro", "Otro"

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="documentos_personales"
    )
    empresa = models.ForeignKey(Empresa, on_delete=models.SET_NULL, null=True, blank=True)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.SET_NULL, null=True, blank=True)

    tipo = models.CharField(max_length=40, choices=Tipos.choices, default=Tipos.OTRO)
    titulo = models.CharField(max_length=180)
    archivo = models.FileField(upload_to="funcionarios/documentos/")
    observacion = models.TextField(blank=True, default="")
    activo = models.BooleanField(default=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado_en"]

    def save(self, *args, **kwargs):
        if self.funcionario and self.funcionario.sucursal_rel:
            self.empresa = self.funcionario.sucursal_rel.empresa
            self.sucursal = self.funcionario.sucursal_rel
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.titulo}"


class HistorialLaboralFuncionario(models.Model):
    class Tipos(models.TextChoices):
        INGRESO = "ingreso", "Ingreso"
        ASCENSO = "ascenso", "Ascenso"
        TRASLADO = "traslado", "Traslado"
        CAMBIO_CARGO = "cambio_cargo", "Cambio de cargo"
        CAMBIO_SUCURSAL = "cambio_sucursal", "Cambio de sucursal"
        REINCORPORACION = "reincorporacion", "Reincorporación"
        OTRO = "otro", "Otro"

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="historial_laboral"
    )
    empresa = models.ForeignKey(Empresa, on_delete=models.SET_NULL, null=True, blank=True)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.SET_NULL, null=True, blank=True)

    fecha = models.DateField(default=timezone.localdate)
    tipo = models.CharField(max_length=40, choices=Tipos.choices, default=Tipos.OTRO)
    titulo = models.CharField(max_length=180)
    descripcion = models.TextField(blank=True, default="")
    adjunto = models.FileField(upload_to="funcionarios/historial_laboral/", null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-creado_en"]

    def save(self, *args, **kwargs):
        if self.funcionario and self.funcionario.sucursal_rel:
            self.empresa = self.funcionario.sucursal_rel.empresa
            self.sucursal = self.funcionario.sucursal_rel
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.titulo}"


class ConductaFuncionario(models.Model):
    class Tipos(models.TextChoices):
        RECONOCIMIENTO = "reconocimiento", "Reconocimiento"
        FELICITACION = "felicitacion", "Felicitación"
        OBSERVACION = "observacion", "Observación"
        AMONESTACION = "amonestacion", "Amonestación"
        APERCIBIMIENTO = "apercibimiento", "Apercibimiento"
        SUSPENSION = "suspension", "Suspensión"
        OTRO = "otro", "Otro"

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="conductas"
    )
    empresa = models.ForeignKey(Empresa, on_delete=models.SET_NULL, null=True, blank=True)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.SET_NULL, null=True, blank=True)

    fecha = models.DateField(default=timezone.localdate)
    tipo = models.CharField(max_length=40, choices=Tipos.choices, default=Tipos.OBSERVACION)
    titulo = models.CharField(max_length=180)
    descripcion = models.TextField()
    adjunto = models.FileField(upload_to="funcionarios/conducta/", null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-creado_en"]

    def save(self, *args, **kwargs):
        if self.funcionario and self.funcionario.sucursal_rel:
            self.empresa = self.funcionario.sucursal_rel.empresa
            self.sucursal = self.funcionario.sucursal_rel
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.get_tipo_display()}"


class HistorialSalarialFuncionario(models.Model):
    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="historial_salarial"
    )
    empresa = models.ForeignKey(Empresa, on_delete=models.SET_NULL, null=True, blank=True)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.SET_NULL, null=True, blank=True)

    fecha = models.DateField(default=timezone.localdate)
    salario_anterior = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    salario_nuevo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bono_anterior = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bono_nuevo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    motivo = models.CharField(max_length=180, blank=True, default="")
    observacion = models.TextField(blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-creado_en"]

    def save(self, *args, **kwargs):
        if self.funcionario and self.funcionario.sucursal_rel:
            self.empresa = self.funcionario.sucursal_rel.empresa
            self.sucursal = self.funcionario.sucursal_rel
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.fecha}"


class Asistencia(models.Model):
    ORIGEN_MARCACION_CHOICES = [
        ("lector", "Lector facial"),
        ("biometrico_tablet", "Biométrico tablet"),
        ("biometrico_celular", "Biométrico celular"),
        ("manual", "Manual"),
    ]

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

    origen_marcacion = models.CharField(
        max_length=20,
        choices=ORIGEN_MARCACION_CHOICES,
        default="lector"
    )

    marcado_manual_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marcaciones_manuales"
    )

    empresa = models.ForeignKey(
        "core.Empresa",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="asistencias"
    )

    motivo_marcacion_manual = models.TextField(blank=True, null=True)
    fecha_hora_real_sistema = models.DateTimeField(blank=True, null=True)

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
    def es_manual(self):
        return self.origen_marcacion == "manual"

    @property
    def operador_manual_nombre(self):
        if not self.marcado_manual_por:
            return "-"
        nombre = self.marcado_manual_por.get_full_name()
        return nombre or self.marcado_manual_por.username

    @property
    def auditoria_manual_texto(self):
        if not self.es_manual:
            return ""

        partes = []

        if self.operador_manual_nombre:
            partes.append(f"Operador: {self.operador_manual_nombre}")

        if self.fecha_hora_real_sistema:
            partes.append(
                f"Sistema: {timezone.localtime(self.fecha_hora_real_sistema).strftime('%d/%m/%Y %H:%M:%S')}"
            )

        if self.motivo_marcacion_manual:
            partes.append(f"Motivo: {self.motivo_marcacion_manual}")

        return " | ".join(partes)

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
    
    def save(self, *args, **kwargs):
        if self.funcionario and self.funcionario.sucursal_rel:
            self.empresa = self.funcionario.sucursal_rel.empresa
        super().save(*args, **kwargs)
        


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

    empresa = models.ForeignKey(
        "core.Empresa",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="deudas"
    )

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
    
    def save(self, *args, **kwargs):
        if self.funcionario and self.funcionario.sucursal_rel:
            self.empresa = self.funcionario.sucursal_rel.empresa

        super().save(*args, **kwargs)


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

    empresa = models.ForeignKey(
        "core.Empresa",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="nominas"
    )

    class Meta:
        ordering = ["-anio", "-mes", "funcionario__apellido", "funcionario__nombre"]
        unique_together = ("funcionario", "mes", "anio")

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - Nómina {self.mes:02d}/{self.anio}"
    
    def save(self, *args, **kwargs):
        if self.funcionario and self.funcionario.sucursal_rel:
            self.empresa = self.funcionario.sucursal_rel.empresa
        super().save(*args, **kwargs)
    
class AguinaldoAnual(models.Model):
    class Estados(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PAGADO = "pagado", "Pagado"
        ANULADO = "anulado", "Anulado"

    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name="aguinaldos")
    empresa = models.ForeignKey(Empresa, on_delete=models.SET_NULL, null=True, blank=True, related_name="aguinaldos")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.SET_NULL, null=True, blank=True, related_name="aguinaldos")

    anio = models.PositiveIntegerField()
    total_remuneraciones = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monto_aguinaldo = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    meses_computados = models.PositiveSmallIntegerField(default=0)

    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.PENDIENTE)
    fecha_pago = models.DateField(null=True, blank=True)
    observacion = models.TextField(blank=True, default="")

    generado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-anio", "funcionario__apellido", "funcionario__nombre"]
        unique_together = ("funcionario", "anio")

    def __str__(self):
        return f"Aguinaldo {self.anio} - {self.funcionario.nombre_completo}"
    
class PlanillaBancaria(models.Model):
    class Estados(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        GENERADA = "generada", "Generada"
        EXPORTADA = "exportada", "Exportada"

    class Formatos(models.TextChoices):
        CSV = "csv", "CSV"
        TXT = "txt", "TXT"

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planillas_bancarias"
    )

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planillas_bancarias"
    )

    anio = models.PositiveIntegerField()
    mes = models.PositiveSmallIntegerField()

    banco = models.CharField(max_length=120)
    formato = models.CharField(
        max_length=10,
        choices=Formatos.choices,
        default=Formatos.CSV
    )

    total_funcionarios = models.PositiveIntegerField(default=0)
    total_importe = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    observacion = models.TextField(blank=True, default="")

    estado = models.CharField(
        max_length=20,
        choices=Estados.choices,
        default=Estados.BORRADOR
    )

    generado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planillas_bancarias_generadas"
    )

    generado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-anio", "-mes", "-generado_en"]

    def __str__(self):
        return f"{self.banco} - {self.mes:02d}/{self.anio}"
    
class BancoHorasMovimiento(models.Model):
    class Tipos(models.TextChoices):
        GENERADO = "generado", "Horas generadas"
        DESCUENTO = "descuento", "Descuento por faltante"
        HORAS_TOMADAS = "horas_tomadas", "Horas tomadas"
        AJUSTE_MANUAL = "ajuste_manual", "Ajuste manual"

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="movimientos_banco_horas"
    )

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_banco_horas"
    )

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_banco_horas"
    )

    fecha = models.DateField(default=timezone.localdate)

    tipo = models.CharField(
        max_length=30,
        choices=Tipos.choices
    )

    minutos = models.IntegerField(default=0)

    saldo_anterior = models.IntegerField(default=0)
    saldo_nuevo = models.IntegerField(default=0)

    origen = models.CharField(max_length=50, blank=True, default="sistema")
    observacion = models.TextField(blank=True, default="")

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_banco_horas_creados"
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-creado_en"]

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.get_tipo_display()}"

    @property
    def horas_texto(self):
        horas = abs(self.minutos) // 60
        minutos = abs(self.minutos) % 60
        signo = "-" if self.minutos < 0 else "+"
        return f"{signo}{horas:02d}:{minutos:02d}"
    
class CierreNomina(models.Model):
    mes = models.PositiveSmallIntegerField()
    anio = models.PositiveIntegerField()
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True)
    cerrado = models.BooleanField(default=True)
    cerrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    cerrado_en = models.DateTimeField(default=timezone.now)
    observacion = models.TextField(blank=True, default="")

    class Meta:
        unique_together = ("mes", "anio", "empresa")
        ordering = ["-anio", "-mes"]

    def __str__(self):
        empresa = self.empresa.nombre if self.empresa else "Global"
        return f"Nómina {self.mes:02d}/{self.anio} - {empresa}"    


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

    empresa = models.ForeignKey(
        "core.Empresa",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_items"
    )

    class Meta:
        ordering = ["-fecha_desde", "-creado_en"]

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.get_tipo_display()} ({self.fecha_desde} a {self.fecha_hasta})"

    @property
    def dias(self):
        return (self.fecha_hasta - self.fecha_desde).days + 1
    
    def save(self, *args, **kwargs):
        if self.funcionario and self.funcionario.sucursal_rel:
            self.empresa = self.funcionario.sucursal_rel.empresa
        super().save(*args, **kwargs)


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
    fecha_notificacion = models.DateField(null=True, blank=True)
    dias_solicitados = models.PositiveIntegerField(default=1)
    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.PENDIENTE)
    observacion = models.TextField(blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    empresa = models.ForeignKey(
        "core.Empresa",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="vacaciones"
    )

    def save(self, *args, **kwargs):
        if self.fecha_desde:
            self.fecha_notificacion = self.fecha_desde - timedelta(days=15)

        if self.funcionario and self.funcionario.sucursal_rel:
            self.empresa = self.funcionario.sucursal_rel.empresa

        super().save(*args, **kwargs)

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
    empresa = models.ForeignKey(
        Empresa,
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
    
class Liquidacion(models.Model):
    class TiposSalida(models.TextChoices):
        DESPIDO_JUSTA_CAUSA = "despido_justa_causa", "Despido por Justa Causa"
        PERIODO_PRUEBA = "periodo_prueba", "Periodo de Prueba"
        DESPIDO_SIN_JUSTA_CAUSA = "despido_sin_justa_causa", "Despido sin Justa Causa"
        RENUNCIA = "renuncia", "Renuncia"
        ABANDONO = "abandono", "Abandono"

    class Estados(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        CONFIRMADA = "confirmada", "Confirmada"
        PAGADA = "pagada", "Pagada"
        ANULADA = "anulada", "Anulada"

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="liquidaciones"
    )

    fecha_salida = models.DateField()
    fecha_calculo = models.DateField(default=timezone.localdate)

    tipo_salida = models.CharField(max_length=40, choices=TiposSalida.choices)
    motivo_observacion = models.TextField(blank=True, default="")

    modalidad_salarial_snapshot = models.CharField(max_length=30, blank=True, default="normal")
    salario_base_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bono_base_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    salario_diferenciado_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    salario_bruto_aplicable_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    porcentaje_ips_snapshot = models.DecimalField(max_digits=5, decimal_places=2, default=9)
    descuento_ips_calculado_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    antiguedad_anios = models.PositiveIntegerField(default=0)
    antiguedad_meses = models.PositiveIntegerField(default=0)
    antiguedad_dias = models.PositiveIntegerField(default=0)

    dias_trabajados_pendientes = models.PositiveIntegerField(default=0)
    salario_pendiente_monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    ausencias_descuento = models.PositiveIntegerField(default=0)
    descuento_ausencias = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    vacaciones_causadas_pendientes_dias = models.PositiveIntegerField(default=0)
    vacaciones_causadas_monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    vacaciones_proporcionales_dias = models.PositiveIntegerField(default=0)
    vacaciones_proporcionales_monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    aguinaldo_proporcional_monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    preaviso_dias_corresponde = models.PositiveIntegerField(default=0)
    preaviso_dias_otorgados = models.PositiveIntegerField(default=0)
    preaviso_cumplido = models.BooleanField(default=False)
    descontar_preaviso = models.BooleanField(default=False)
    preaviso_monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    indemnizacion_dias = models.PositiveIntegerField(default=0)
    indemnizacion_monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    ips_monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deudas_monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    otros_descuentos = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    total_haberes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_descuentos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_liquidacion = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_haberes_automatico = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_descuentos_automatico = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_liquidacion_automatico = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    requiere_revision_juridica = models.BooleanField(default=False)
    alerta_revision = models.CharField(max_length=255, blank=True, default="")

    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.BORRADOR)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    empresa = models.ForeignKey(
        "core.Empresa",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="liquidaciones"
    )

    class Meta:
        ordering = ["-fecha_calculo", "-creado_en"]

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.get_tipo_salida_display()} - {self.fecha_salida:%d/%m/%Y}"
    
    def save(self, *args, **kwargs):
        if self.funcionario and self.funcionario.sucursal_rel:
            self.empresa = self.funcionario.sucursal_rel.empresa
        super().save(*args, **kwargs)


class AjusteManualLiquidacion(models.Model):
    class Tipos(models.TextChoices):
        HABER = "haber", "Haber"
        DESCUENTO = "descuento", "Descuento"

    class Estados(models.TextChoices):
        ACTIVO = "activo", "Activo"
        ANULADO = "anulado", "Anulado"

    liquidacion = models.ForeignKey(
        Liquidacion,
        on_delete=models.CASCADE,
        related_name="ajustes_manuales"
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="ajustes_liquidacion"
    )
    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="ajustes_liquidacion"
    )
    tipo = models.CharField(max_length=20, choices=Tipos.choices)
    concepto = models.CharField(max_length=150)
    importe_anterior = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    importe_nuevo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    diferencia = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    motivo = models.TextField()
    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.ACTIVO)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ajustes_liquidacion_creados"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ajustes_liquidacion_anulados"
    )
    anulado_en = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.concepto} - {self.liquidacion_id}"

    def save(self, *args, **kwargs):
        self.diferencia = (
            Decimal(self.importe_nuevo or 0) - Decimal(self.importe_anterior or 0)
        ).quantize(Decimal("0.01"))

        if self.liquidacion_id:
            self.funcionario = self.liquidacion.funcionario
            self.empresa = self.liquidacion.empresa or self.liquidacion.funcionario.empresa

        super().save(*args, **kwargs)


class DiaLibre(models.Model):
    class DiasSemana(models.IntegerChoices):
        LUNES = 0, "Lunes"
        MARTES = 1, "Martes"
        MIERCOLES = 2, "Miércoles"
        JUEVES = 3, "Jueves"
        VIERNES = 4, "Viernes"
        SABADO = 5, "Sábado"
        DOMINGO = 6, "Domingo"

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="dias_libres"
    )

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dias_libres"
    )

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dias_libres"
    )

    sector = models.CharField(max_length=100, blank=True, default="")
    dia_semana = models.PositiveSmallIntegerField(choices=DiasSemana.choices)

    fecha_inicio = models.DateField(default=timezone.localdate)
    fecha_fin = models.DateField(null=True, blank=True)

    activo = models.BooleanField(default=True)
    observacion = models.CharField(max_length=255, blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sector", "dia_semana", "funcionario__apellido", "funcionario__nombre"]
        unique_together = ("funcionario", "activo")

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.get_dia_semana_display()}"

    @property
    def vigente(self):
        hoy = timezone.localdate()
        if not self.activo:
            return False
        if self.fecha_inicio and self.fecha_inicio > hoy:
            return False
        if self.fecha_fin and self.fecha_fin < hoy:
            return False
        return True    
    
class PlanillaSemanalFuncionario(models.Model):
    funcionario = models.OneToOneField(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="planilla_semanal"
    )

    lunes = models.ForeignKey(Turno, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    martes = models.ForeignKey(Turno, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    miercoles = models.ForeignKey(Turno, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    jueves = models.ForeignKey(Turno, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    viernes = models.ForeignKey(Turno, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    sabado = models.ForeignKey(Turno, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    domingo = models.ForeignKey(Turno, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["funcionario__apellido", "funcionario__nombre"]

    def __str__(self):
        return f"Planilla semanal - {self.funcionario.nombre_completo}"

    def turno_para_fecha(self, fecha):
        dia = fecha.weekday()

        mapa = {
            0: self.lunes,
            1: self.martes,
            2: self.miercoles,
            3: self.jueves,
            4: self.viernes,
            5: self.sabado,
            6: self.domingo,
        }

        return mapa.get(dia)
class ComunicacionLaboral(models.Model):
    class Tipos(models.TextChoices):
        AMONESTACION = "amonestacion", "Sanción Disciplinaria / Amonestación"
        PREAVISO = "preaviso", "Preaviso"
        ABANDONO = "abandono", "Abandono de Trabajo"
        PERMISO = "permiso", "Comunicación de Permiso"
        AUSENCIA = "ausencia", "Ausencia Injustificada"
        SUSPENSION = "suspension", "Suspensión Disciplinaria"
        CITACION_DESCARGO = "citacion_descargo", "Citación a Descargo"
        CAMBIO_CARGO_SECTOR = "cambio_cargo_sector", "Cambio de Cargo / Sector / Sucursal"
        MEMORANDUM = "memorandum", "Memorándum Interno"

    class Estados(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        EMITIDA = "emitida", "Emitida"
        ENTREGADA = "entregada", "Entregada"
        FIRMADA = "firmada", "Firmada"
        ANULADA = "anulada", "Anulada"

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="comunicaciones"
    )

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comunicaciones"
    )

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comunicaciones"
    )

    tipo = models.CharField(max_length=40, choices=Tipos.choices)
    titulo = models.CharField(max_length=180)
    fecha_emision = models.DateField(default=timezone.localdate)
    fecha_referencia = models.DateField(null=True, blank=True)

    asunto = models.CharField(max_length=255, blank=True, default="")
    detalle_hecho = models.TextField(blank=True, default="")
    contenido = models.TextField(blank=True, default="")
    observacion_interna = models.TextField(blank=True, default="")

    requiere_firma = models.BooleanField(default=True)
    firmado = models.BooleanField(default=False)
    fecha_firma = models.DateField(null=True, blank=True)

    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.BORRADOR)

    generado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comunicaciones_generadas"
    )

    adjunto_firmado = models.FileField(
        upload_to="comunicaciones/firmadas/",
        null=True,
        blank=True
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_emision", "-creado_en"]

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.get_tipo_display()} - {self.fecha_emision:%d/%m/%Y}"
    
class DocumentoFirmado(models.Model):
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="documentos_firmados"
    )

    codigo = models.CharField(max_length=80, unique=True)
    tipo_documento = models.CharField(max_length=80)
    documento_id = models.PositiveIntegerField(null=True, blank=True)

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_firmados"
    )

    titulo = models.CharField(max_length=180, blank=True, default="")
    hash_documento = models.CharField(max_length=128, blank=True, default="")

    firmado_por_nombre = models.CharField(max_length=150, blank=True, default="")
    firmado_por_cargo = models.CharField(max_length=150, blank=True, default="")

    emitido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_emitidos"
    )

    emitido_en = models.DateTimeField(auto_now_add=True)
    valido = models.BooleanField(default=True)

    class Meta:
        ordering = ["-emitido_en"]

    def __str__(self):
        return f"{self.codigo} - {self.tipo_documento}"


class SuscripcionSistema(models.Model):
    class Estados(models.TextChoices):
        ACTIVA = "activa", "Activa"
        PAUSADA = "pausada", "Pausada"

    nombre_cliente = models.CharField(max_length=150, blank=True, default="ClockIn")
    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.ACTIVA)
    fecha_inicio = models.DateField(default=timezone.localdate)
    fecha_proximo_pago = models.DateField(default=timezone.localdate)
    fecha_ultimo_pago = models.DateField(null=True, blank=True)
    dias_gracia = models.PositiveIntegerField(default=0)
    bloquear_al_vencer = models.BooleanField(default=True)
    contacto_pago = models.CharField(max_length=180, blank=True, default="")
    mensaje_bloqueo = models.TextField(
        blank=True,
        default="El servicio se encuentra pendiente de regularizacion. Contacte al administrador para reactivar el acceso."
    )
    observacion_interna = models.TextField(blank=True, default="")
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suscripciones_actualizadas"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Suscripcion del sistema"
        verbose_name_plural = "Suscripciones del sistema"

    def __str__(self):
        return f"Suscripcion {self.nombre_cliente} - {self.estado_visible}"

    @classmethod
    def obtener(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "nombre_cliente": "ClockIn",
                "fecha_inicio": timezone.localdate(),
                "fecha_proximo_pago": timezone.localdate() + timezone.timedelta(days=30),
                "dias_gracia": 0,
                "bloquear_al_vencer": True,
            }
        )
        return obj

    @property
    def fecha_bloqueo(self):
        return self.fecha_proximo_pago + timezone.timedelta(days=int(self.dias_gracia or 0))

    @property
    def dias_restantes(self):
        return (self.fecha_proximo_pago - timezone.localdate()).days

    @property
    def dias_para_bloqueo(self):
        return (self.fecha_bloqueo - timezone.localdate()).days

    @property
    def vencida(self):
        return self.dias_restantes < 0

    @property
    def en_gracia(self):
        return self.vencida and self.dias_para_bloqueo >= 0

    @property
    def bloqueada(self):
        if self.estado != self.Estados.ACTIVA:
            return True
        if not self.bloquear_al_vencer:
            return False
        return timezone.localdate() > self.fecha_bloqueo

    @property
    def por_vencer(self):
        return 0 <= self.dias_restantes <= 5

    @property
    def estado_visible(self):
        if self.bloqueada:
            return "Bloqueada"
        if self.en_gracia:
            return "En periodo de gracia"
        if self.por_vencer:
            return "Por vencer"
        return self.get_estado_display()


class PagoSuscripcionSistema(models.Model):
    class Periodos(models.IntegerChoices):
        MENSUAL = 1, "Mensual"
        TRIMESTRAL = 3, "Trimestral"
        SEMESTRAL = 6, "Semestral"
        ANUAL = 12, "Anual"

    suscripcion = models.ForeignKey(
        SuscripcionSistema,
        on_delete=models.CASCADE,
        related_name="pagos"
    )
    fecha_pago = models.DateField(default=timezone.localdate)
    meses_cubiertos = models.PositiveSmallIntegerField(choices=Periodos.choices, default=Periodos.MENSUAL)
    monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    comprobante = models.CharField(max_length=120, blank=True, default="")
    observacion = models.TextField(blank=True, default="")
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagos_suscripcion_registrados"
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_pago", "-creado_en"]
        verbose_name = "Pago de suscripcion"
        verbose_name_plural = "Pagos de suscripcion"

    def __str__(self):
        return f"Pago {self.fecha_pago:%d/%m/%Y} - {self.get_meses_cubiertos_display()}"

class Diarista(models.Model):
    class Estados(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        ACTIVO = "activo", "Activo"
        FINALIZADO = "finalizado", "Finalizado"
        CANCELADO = "cancelado", "Cancelado"

    class FormasCalculo(models.TextChoices):
        POR_DIA_TRABAJADO = "por_dia_trabajado", "Por día efectivamente trabajado"
        POR_DIAS_CONTRATADOS = "por_dias_contratados", "Por días contratados"

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="diaristas"
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diaristas"
    )
    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120)
    cedula = models.CharField(max_length=30)
    telefono = models.CharField(max_length=50, blank=True, default="")
    direccion = models.CharField(max_length=255, blank=True, default="")
    fecha_nacimiento = models.DateField(null=True, blank=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    cantidad_dias_contratados = models.PositiveIntegerField(default=1)
    monto_diario_acordado = models.DecimalField(max_digits=12, decimal_places=2)
    forma_calculo = models.CharField(
        max_length=30,
        choices=FormasCalculo.choices,
        default=FormasCalculo.POR_DIA_TRABAJADO
    )
    turno = models.ForeignKey(
        Turno,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diaristas"
    )
    sector = models.CharField(max_length=100, blank=True, default="")
    funcion_temporal = models.CharField(max_length=150, blank=True, default="")
    observaciones = models.TextField(blank=True, default="")
    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.PENDIENTE)
    activo = models.BooleanField(default=True)
    face_encoding = models.BinaryField(null=True, blank=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diaristas_creados"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_inicio", "apellidos", "nombres"]
        indexes = [
            models.Index(fields=["empresa", "estado", "fecha_inicio"]),
            models.Index(fields=["empresa", "cedula"]),
            models.Index(fields=["sucursal", "estado"]),
        ]
        verbose_name = "Diarista"
        verbose_name_plural = "Diaristas"

    def __str__(self):
        return f"{self.nombre_completo} - CI: {self.cedula}"

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}".strip()

    @property
    def esta_vigente(self):
        hoy = timezone.localdate()
        if self.estado != self.Estados.ACTIVO:
            return False
        if self.fecha_inicio and hoy < self.fecha_inicio:
            return False
        if self.fecha_fin and hoy > self.fecha_fin:
            return False
        return True

    @property
    def total_estimado(self):
        return (self.monto_diario_acordado or Decimal("0")) * Decimal(self.cantidad_dias_contratados or 0)


class PagoDiarista(models.Model):
    class Estados(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        GENERADO = "generado", "Generado"
        PAGADO = "pagado", "Pagado"
        ANULADO = "anulado", "Anulado"

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="pagos_diaristas"
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagos_diaristas"
    )
    diarista = models.ForeignKey(
        Diarista,
        on_delete=models.CASCADE,
        related_name="pagos"
    )
    fecha_pago = models.DateField(default=timezone.localdate)
    periodo_desde = models.DateField()
    periodo_hasta = models.DateField()
    dias_calculados = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    monto_diario_aplicado = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    adicionales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    descuentos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    observacion = models.TextField(blank=True, default="")
    concepto_adicional = models.CharField(max_length=180, blank=True, default="")
    motivo_ajuste = models.TextField(blank=True, default="")
    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.BORRADOR)
    numero_comprobante = models.CharField(max_length=30, unique=True, null=True, blank=True)
    generado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagos_diaristas_generados"
    )
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagos_diaristas_anulados"
    )
    motivo_anulacion = models.TextField(blank=True, default="")
    fecha_anulacion = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_pago", "-creado_en"]
        indexes = [
            models.Index(fields=["empresa", "estado", "fecha_pago"]),
            models.Index(fields=["diarista", "estado"]),
            models.Index(fields=["numero_comprobante"]),
        ]
        verbose_name = "Pago de diarista"
        verbose_name_plural = "Pagos de diaristas"

    def __str__(self):
        numero = self.numero_comprobante or "Sin número"
        return f"{numero} - {self.diarista.nombre_completo}"

    def calcular_total(self):
        self.subtotal = (self.dias_calculados or Decimal("0")) * (self.monto_diario_aplicado or Decimal("0"))
        self.total_pagado = self.subtotal + (self.adicionales or Decimal("0")) - (self.descuentos or Decimal("0"))
        return self.total_pagado


class AsistenciaDiarista(models.Model):
    class Estados(models.TextChoices):
        PROGRAMADO = "programado", "Programado"
        TRABAJADO = "trabajado", "Trabajado"
        AUSENTE = "ausente", "Ausente"
        INCOMPLETO = "incompleto", "Incompleto"

    class EstadosPago(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente de pago"
        INCLUIDO = "incluido", "Incluido en pago"
        PAGADO = "pagado", "Pagado"
        REABIERTO = "reabierto", "Reabierto"

    ORIGEN_CHOICES = [
        ("manual", "Manual"),
        ("biometrico_tablet", "Biométrico tablet"),
        ("biometrico_celular", "Biométrico celular"),
    ]

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="asistencias_diaristas"
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asistencias_diaristas"
    )
    diarista = models.ForeignKey(
        Diarista,
        on_delete=models.CASCADE,
        related_name="asistencias"
    )
    fecha = models.DateField()
    hora_entrada = models.DateTimeField(null=True, blank=True)
    hora_salida = models.DateTimeField(null=True, blank=True)
    minutos_trabajados = models.PositiveIntegerField(default=0)
    minutos_atraso = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.PROGRAMADO)
    pago_estado = models.CharField(max_length=20, choices=EstadosPago.choices, default=EstadosPago.PENDIENTE)
    pago = models.ForeignKey(
        PagoDiarista,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jornadas"
    )
    origen_marcacion = models.CharField(max_length=20, choices=ORIGEN_CHOICES, default="manual")
    observacion = models.TextField(blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha", "diarista__apellidos", "diarista__nombres"]
        constraints = [
            models.UniqueConstraint(fields=["diarista", "fecha"], name="uniq_asistencia_diarista_fecha"),
        ]
        indexes = [
            models.Index(fields=["empresa", "fecha", "estado"]),
            models.Index(fields=["diarista", "fecha"]),
            models.Index(fields=["pago_estado"]),
        ]
        verbose_name = "Asistencia de diarista"
        verbose_name_plural = "Asistencias de diaristas"

    def __str__(self):
        return f"{self.diarista.nombre_completo} - {self.fecha:%d/%m/%Y}"

    @property
    def horas_trabajadas_display(self):
        horas = int((self.minutos_trabajados or 0) // 60)
        minutos = int((self.minutos_trabajados or 0) % 60)
        return f"{horas}h {minutos:02d}m"

    def recalcular_minutos_trabajados(self):
        if self.hora_entrada and self.hora_salida and self.hora_salida >= self.hora_entrada:
            delta = self.hora_salida - self.hora_entrada
            self.minutos_trabajados = int(delta.total_seconds() // 60)
            self.estado = self.Estados.TRABAJADO
        elif self.hora_entrada or self.hora_salida:
            self.estado = self.Estados.INCOMPLETO
        return self.minutos_trabajados

