from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import Asistencia, ComunicacionLaboral, DocumentoFuncionario, Empresa, Funcionario


class PortalDocumentoLectura(models.Model):
    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="portal_documentos_lectura",
    )
    documento = models.ForeignKey(
        DocumentoFuncionario,
        on_delete=models.CASCADE,
        related_name="portal_lecturas",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_documentos_leidos",
    )
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="portal_documentos_lectura")

    leido = models.BooleanField(default=False)
    leido_en = models.DateTimeField(null=True, blank=True)
    confirmado = models.BooleanField(default=False)
    confirmado_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("funcionario", "documento")
        ordering = ["-actualizado_en"]

    def marcar_leido(self, usuario=None):
        if not self.leido:
            self.leido = True
            self.leido_en = timezone.now()
        if usuario:
            self.usuario = usuario
        self.save(update_fields=["leido", "leido_en", "usuario", "actualizado_en"])

    def confirmar(self, usuario=None):
        if not self.leido:
            self.leido = True
            self.leido_en = timezone.now()
        self.confirmado = True
        self.confirmado_en = timezone.now()
        if usuario:
            self.usuario = usuario
        self.save(update_fields=["leido", "leido_en", "confirmado", "confirmado_en", "usuario", "actualizado_en"])


class PortalComunicacionLectura(models.Model):
    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="portal_comunicaciones_lectura",
    )
    comunicacion = models.ForeignKey(
        ComunicacionLaboral,
        on_delete=models.CASCADE,
        related_name="portal_lecturas",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_comunicaciones_leidas",
    )
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="portal_comunicaciones_lectura")

    abierto = models.BooleanField(default=False)
    abierto_en = models.DateTimeField(null=True, blank=True)
    confirmado = models.BooleanField(default=False)
    confirmado_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("funcionario", "comunicacion")
        ordering = ["-actualizado_en"]

    def marcar_abierto(self, usuario=None):
        if not self.abierto:
            self.abierto = True
            self.abierto_en = timezone.now()
        if usuario:
            self.usuario = usuario
        self.save(update_fields=["abierto", "abierto_en", "usuario", "actualizado_en"])

    def confirmar(self, usuario=None):
        if not self.abierto:
            self.abierto = True
            self.abierto_en = timezone.now()
        self.confirmado = True
        self.confirmado_en = timezone.now()
        if usuario:
            self.usuario = usuario
        self.save(update_fields=["abierto", "abierto_en", "confirmado", "confirmado_en", "usuario", "actualizado_en"])


class PortalSolicitudDocumento(models.Model):
    class Tipos(models.TextChoices):
        CERTIFICADO_LABORAL = "certificado_laboral", "Certificado laboral"
        CONSTANCIA_ANTIGUEDAD = "constancia_antiguedad", "Constancia de antigüedad"
        CONSTANCIA_HORARIO = "constancia_horario", "Constancia de horario"
        CONSTANCIA_BANCO = "constancia_banco", "Constancia para banco"
        COPIA_CONTRATO = "copia_contrato", "Copia de contrato"
        OTRO = "otro", "Otro"

    class Estados(models.TextChoices):
        SOLICITADO = "solicitado", "Solicitado"
        EN_PREPARACION = "en_preparacion", "En preparación"
        LISTO = "listo", "Listo"
        RECHAZADO = "rechazado", "Rechazado"
        CANCELADO = "cancelado", "Cancelado"

    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name="portal_solicitudes_documentos")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="portal_solicitudes_documentos")
    tipo = models.CharField(max_length=40, choices=Tipos.choices)
    motivo = models.TextField(blank=True, default="")
    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.SOLICITADO)
    observacion_operador = models.TextField(blank=True, default="")
    archivo_final = models.FileField(upload_to="portal/documentos_finales/", null=True, blank=True)
    documento_generado = models.ForeignKey(
        DocumentoFuncionario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_portal",
    )
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_documentos_solicitados",
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_documentos_revisados",
    )
    revisado_en = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado_en"]

    def save(self, *args, **kwargs):
        if self.funcionario and self.funcionario.empresa:
            self.empresa = self.funcionario.empresa
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.get_tipo_display()}"


class PortalSolicitudMarcacion(models.Model):
    class Tipos(models.TextChoices):
        ENTRADA = "entrada", "Entrada"
        SALIDA_ALMUERZO = "salida_almuerzo", "Salida a almuerzo"
        REGRESO_ALMUERZO = "regreso_almuerzo", "Regreso de almuerzo"
        SALIDA = "salida", "Salida"
        OTRO = "otro", "Otro"

    class Estados(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_REVISION = "en_revision", "En revisión"
        APROBADO = "aprobado", "Aprobado"
        RECHAZADO = "rechazado", "Rechazado"
        CANCELADO = "cancelado", "Cancelado"

    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name="portal_solicitudes_marcacion")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="portal_solicitudes_marcacion")
    asistencia = models.ForeignKey(
        Asistencia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_correccion_portal",
    )
    fecha = models.DateField()
    tipo = models.CharField(max_length=30, choices=Tipos.choices)
    hora_solicitada = models.TimeField(null=True, blank=True)
    motivo = models.TextField()
    adjunto = models.FileField(upload_to="portal/marcaciones/", null=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.PENDIENTE)
    observacion_operador = models.TextField(blank=True, default="")
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_marcaciones_solicitadas",
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_marcaciones_revisadas",
    )
    revisado_en = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado_en"]

    def save(self, *args, **kwargs):
        if self.funcionario and self.funcionario.empresa:
            self.empresa = self.funcionario.empresa
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.fecha} - {self.get_tipo_display()}"


class PortalSugerencia(models.Model):
    class Categorias(models.TextChoices):
        GENERAL = "general", "General"
        CLIMA = "clima", "Clima laboral"
        SEGURIDAD = "seguridad", "Seguridad"
        PROCESOS = "procesos", "Procesos"
        BENEFICIOS = "beneficios", "Beneficios"
        OTRO = "otro", "Otro"

    class Estados(models.TextChoices):
        RECIBIDA = "recibida", "Recibida"
        EN_REVISION = "en_revision", "En revisión"
        RESPONDIDA = "respondida", "Respondida"
        CERRADA = "cerrada", "Cerrada"
        ANULADA = "anulada", "Anulada"

    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name="portal_sugerencias")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="portal_sugerencias")
    categoria = models.CharField(max_length=30, choices=Categorias.choices, default=Categorias.GENERAL)
    asunto = models.CharField(max_length=180)
    mensaje = models.TextField()
    adjunto = models.FileField(upload_to="portal/sugerencias/", null=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.RECIBIDA)
    respuesta_operador = models.TextField(blank=True, default="")
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_sugerencias_enviadas",
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_sugerencias_revisadas",
    )
    revisado_en = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado_en"]

    def save(self, *args, **kwargs):
        if self.funcionario and self.funcionario.empresa:
            self.empresa = self.funcionario.empresa
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.asunto}"


class PortalDescargoComunicacion(models.Model):
    class Estados(models.TextChoices):
        ENVIADO = "enviado", "Enviado"
        REVISADO = "revisado", "Revisado"
        ANULADO = "anulado", "Anulado"

    comunicacion = models.ForeignKey(
        ComunicacionLaboral,
        on_delete=models.CASCADE,
        related_name="portal_descargos",
    )
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name="portal_descargos")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="portal_descargos")
    mensaje = models.TextField()
    adjunto = models.FileField(upload_to="portal/descargos/", null=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estados.choices, default=Estados.ENVIADO)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_descargos_enviados",
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_descargos_revisados",
    )
    revisado_en = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado_en"]

    def save(self, *args, **kwargs):
        if self.funcionario and self.funcionario.empresa:
            self.empresa = self.funcionario.empresa
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.funcionario.nombre_completo} - {self.comunicacion.titulo}"
