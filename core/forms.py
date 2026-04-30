from django import forms
from .models import (
    Empresa,
    Sucursal,
    Funcionario,
    Turno,
    Deuda,
    PermisoLicencia,
    Vacacion,
    ConfiguracionGeneral,
    Liquidacion,
    DiaLibre,
)

from django import forms
from django.utils import timezone
from .models import Asistencia


class MarcacionManualForm(forms.Form):
    funcionario = forms.ModelChoiceField(
        queryset=Funcionario.objects.filter(activo=True),
        label="Funcionario",
        widget=forms.Select(attrs={"class": "form-control"})
    )

    tipo = forms.ChoiceField(
        choices=[
            ("entrada", "Entrada"),
            ("salida_almuerzo", "Salida a almuerzo"),
            ("regreso_almuerzo", "Regreso de almuerzo"),
            ("salida", "Salida final"),
        ],
        label="Tipo de marcación",
        widget=forms.Select(attrs={"class": "form-control"})
    )

    fecha = forms.DateField(
        label="Fecha",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "form-control"
        })
    )

    hora = forms.TimeField(
        label="Hora real de llegada/salida",
        widget=forms.TimeInput(attrs={
            "type": "time",
            "class": "form-control"
        })
    )

    motivo = forms.CharField(
        label="Motivo",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 3,
            "placeholder": "Ej: Problema con lector facial, cámara falló, tablet trabada..."
        })
    )

class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = ["nombre", "ruc", "activo"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "ruc": forms.TextInput(attrs={"class": "form-control"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class SucursalForm(forms.ModelForm):
    class Meta:
        model = Sucursal
        fields = ["empresa", "nombre", "direccion", "activo"]
        widgets = {
            "empresa": forms.Select(attrs={"class": "form-control"}),
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "direccion": forms.TextInput(attrs={"class": "form-control"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["empresa"].queryset = Empresa.objects.filter(activo=True).order_by("nombre")
        self.fields["empresa"].empty_label = "Seleccionar empresa"


class TurnoForm(forms.ModelForm):

    class Meta:
        model = Turno
        fields = "__all__"

        widgets = {
            "empresa": forms.Select(attrs={"class": "form-control"}),
            "nombre": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ej: 1er. Turno"
            }),
            "hora_entrada": forms.TimeInput(attrs={
                "type": "time",
                "step": "300",
                "class": "form-control"
            }, format="%H:%M"),
            "hora_salida": forms.TimeInput(attrs={
                "type": "time",
                "step": "300",
                "class": "form-control"
            }, format="%H:%M"),
            "hora_inicio_almuerzo": forms.TimeInput(attrs={
                "type": "time",
                "step": "300",
                "class": "form-control"
            }, format="%H:%M"),
            "hora_fin_almuerzo": forms.TimeInput(attrs={
                "type": "time",
                "step": "300",
                "class": "form-control"
            }, format="%H:%M"),
            "tolerancia_minutos": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "max": "120",
                "placeholder": "Ej: 1"
            }),
            "usa_almuerzo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

        labels = {
            "empresa": "Empresa",
            "nombre": "Nombre del Turno",
            "hora_entrada": "Hora de entrada",
            "hora_salida": "Hora de salida",
            "hora_inicio_almuerzo": "Inicio almuerzo",
            "hora_fin_almuerzo": "Fin almuerzo",
            "tolerancia_minutos": "Tolerancia en minutos",
            "usa_almuerzo": "Usa almuerzo",
            "activo": "Turno activo",
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        for campo in [
            "hora_entrada",
            "hora_salida",
            "hora_inicio_almuerzo",
            "hora_fin_almuerzo",
        ]:
            if campo in self.fields:
                self.fields[campo].input_formats = ["%H:%M"]
                self.fields[campo].required = False

        if "tolerancia_minutos" in self.fields:
            self.fields["tolerancia_minutos"].required = False

        # 🔒 MULTIEMPRESA (BLINDAJE)
        if user:
            if hasattr(user, "empresa") and not user.is_superuser:
                self.fields["empresa"].queryset = self.fields["empresa"].queryset.filter(id=user.empresa.id)
                self.fields["empresa"].initial = user.empresa
                self.fields["empresa"].disabled = True
            else:
                self.fields["empresa"].required = True

    def clean(self):
        cleaned_data = super().clean()

        hora_entrada = cleaned_data.get("hora_entrada")
        hora_salida = cleaned_data.get("hora_salida")
        usa_almuerzo = cleaned_data.get("usa_almuerzo")
        hora_inicio_almuerzo = cleaned_data.get("hora_inicio_almuerzo")
        hora_fin_almuerzo = cleaned_data.get("hora_fin_almuerzo")

        if not hora_entrada:
            self.add_error("hora_entrada", "Debes seleccionar la hora de entrada.")

        if not hora_salida:
            self.add_error("hora_salida", "Debes seleccionar la hora de salida.")

        if hora_entrada and hora_salida and hora_salida <= hora_entrada:
            self.add_error("hora_salida", "La hora de salida debe ser mayor que la hora de entrada.")

        if usa_almuerzo:
            if not hora_inicio_almuerzo:
                self.add_error("hora_inicio_almuerzo", "Debes seleccionar el inicio del almuerzo.")

            if not hora_fin_almuerzo:
                self.add_error("hora_fin_almuerzo", "Debes seleccionar el fin del almuerzo.")

            if hora_entrada and hora_inicio_almuerzo and hora_inicio_almuerzo <= hora_entrada:
                self.add_error("hora_inicio_almuerzo", "El inicio de almuerzo debe ser posterior a la entrada.")

            if hora_inicio_almuerzo and hora_fin_almuerzo and hora_fin_almuerzo <= hora_inicio_almuerzo:
                self.add_error("hora_fin_almuerzo", "El fin de almuerzo debe ser mayor que el inicio de almuerzo.")

            if hora_salida and hora_fin_almuerzo and hora_fin_almuerzo >= hora_salida:
                self.add_error("hora_fin_almuerzo", "El fin de almuerzo debe ser anterior a la salida.")
        else:
            cleaned_data["hora_inicio_almuerzo"] = None
            cleaned_data["hora_fin_almuerzo"] = None

        return cleaned_data


class ConfiguracionGeneralForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionGeneral
        fields = [
            "nombre_sistema",
            "subtitulo_sistema",
            "color_primario",
            "logo_url",

            "salario_base_default",
            "porcentaje_limite_deuda_default",
            "tolerancia_minutos_default",

            "bancos_personalizados",
            "cargos_personalizados",
            "sectores_personalizados",

            "biometrico_segundos_lectura",
            "biometrico_pausa_exito_ms",
            "biometrico_pausa_aviso_ms",
            "biometrico_pausa_error_ms",
            "biometrico_sonidos_activos",
            "biometrico_fullscreen_auto",

            "observacion_general",
        ]
        widgets = {
            "nombre_sistema": forms.TextInput(attrs={"class": "form-control"}),
            "subtitulo_sistema": forms.TextInput(attrs={"class": "form-control"}),
            "color_primario": forms.Select(attrs={"class": "form-control"}),
            "logo_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),

            "salario_base_default": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "porcentaje_limite_deuda_default": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "tolerancia_minutos_default": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),

            "bancos_personalizados": forms.Textarea(attrs={"class": "form-control", "rows": 8}),
            "cargos_personalizados": forms.Textarea(attrs={"class": "form-control", "rows": 12}),
            "sectores_personalizados": forms.Textarea(attrs={"class": "form-control", "rows": 10}),

            "biometrico_segundos_lectura": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "biometrico_pausa_exito_ms": forms.NumberInput(attrs={"class": "form-control", "min": "500"}),
            "biometrico_pausa_aviso_ms": forms.NumberInput(attrs={"class": "form-control", "min": "500"}),
            "biometrico_pausa_error_ms": forms.NumberInput(attrs={"class": "form-control", "min": "500"}),

            "biometrico_sonidos_activos": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "biometrico_fullscreen_auto": forms.CheckboxInput(attrs={"class": "form-check-input"}),

            "observacion_general": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }
        labels = {
            "nombre_sistema": "Nombre del sistema",
            "subtitulo_sistema": "Subtítulo del sistema",
            "color_primario": "Tema visual",
            "logo_url": "URL del logo",

            "salario_base_default": "Salario base global",
            "porcentaje_limite_deuda_default": "Límite de deuda global (%)",
            "tolerancia_minutos_default": "Tolerancia global (minutos)",

            "bancos_personalizados": "Bancos personalizados",
            "cargos_personalizados": "Cargos personalizados",
            "sectores_personalizados": "Sectores personalizados",

            "biometrico_segundos_lectura": "Lectura biométrica (segundos)",
            "biometrico_pausa_exito_ms": "Pausa éxito (ms)",
            "biometrico_pausa_aviso_ms": "Pausa aviso (ms)",
            "biometrico_pausa_error_ms": "Pausa error (ms)",
            "biometrico_sonidos_activos": "Activar sonidos del biométrico",
            "biometrico_fullscreen_auto": "Activar fullscreen automático",

            "observacion_general": "Observación general",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["color_primario"].choices = list(ConfiguracionGeneral.TEMAS_CHOICES)

        mapa_hex_a_tema = {
            "#2563eb": ConfiguracionGeneral.TEMA_AZUL,
            "#16a34a": ConfiguracionGeneral.TEMA_VERDE,
            "#dc2626": ConfiguracionGeneral.TEMA_ROJO,
            "#ea580c": ConfiguracionGeneral.TEMA_NARANJA,
            "#7c3aed": ConfiguracionGeneral.TEMA_MORADO,
            "#0891b2": ConfiguracionGeneral.TEMA_TURQUESA,
            "#475569": ConfiguracionGeneral.TEMA_GRIS,
        }

        valores_validos = {item[0] for item in ConfiguracionGeneral.TEMAS_CHOICES}
        valor_actual = getattr(self.instance, "color_primario", None)

        if valor_actual in mapa_hex_a_tema:
            valor_actual = mapa_hex_a_tema[valor_actual]

        if valor_actual not in valores_validos:
            valor_actual = ConfiguracionGeneral.TEMA_AZUL

        self.initial["color_primario"] = valor_actual

    def _validar_lista(self, valor, nombre, minimo=1):
        items = [x.strip() for x in (valor or "").splitlines() if x.strip()]
        items_unicos = []
        for item in items:
            if item not in items_unicos:
                items_unicos.append(item)

        if len(items_unicos) < minimo:
            raise forms.ValidationError(f"Debes cargar al menos {minimo} opción(es) en {nombre}.")

        if len(items_unicos) > 150:
            raise forms.ValidationError(f"{nombre} tiene demasiadas opciones. Reduce la lista.")

        return "\n".join(items_unicos)

    def clean_biometrico_segundos_lectura(self):
        valor = self.cleaned_data["biometrico_segundos_lectura"]
        if valor < 1:
            raise forms.ValidationError("La lectura biométrica debe ser de al menos 1 segundo.")
        return valor

    def clean_porcentaje_limite_deuda_default(self):
        valor = self.cleaned_data["porcentaje_limite_deuda_default"]
        if valor < 0:
            raise forms.ValidationError("El porcentaje no puede ser negativo.")
        return valor

    def clean_tolerancia_minutos_default(self):
        valor = self.cleaned_data["tolerancia_minutos_default"]
        if valor < 0:
            raise forms.ValidationError("La tolerancia no puede ser negativa.")
        return valor

    def clean_color_primario(self):
        valor = (self.cleaned_data.get("color_primario") or "").strip()
        valores_validos = {item[0] for item in ConfiguracionGeneral.TEMAS_CHOICES}
        if valor not in valores_validos:
            return ConfiguracionGeneral.TEMA_AZUL
        return valor

    def clean_bancos_personalizados(self):
        return self._validar_lista(
            self.cleaned_data.get("bancos_personalizados"),
            "bancos personalizados"
        )

    def clean_cargos_personalizados(self):
        return self._validar_lista(
            self.cleaned_data.get("cargos_personalizados"),
            "cargos personalizados"
        )

    def clean_sectores_personalizados(self):
        return self._validar_lista(
            self.cleaned_data.get("sectores_personalizados"),
            "sectores personalizados"
        )


class FuncionarioForm(forms.ModelForm):
    empresa = forms.ModelChoiceField(
        queryset=Empresa.objects.filter(activo=True).order_by("nombre"),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"})
    )

    salario_base_fijo = forms.CharField(
        required=False,
        label="Salario base",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "readonly": "readonly",
        })
    )

    fecha_ingreso = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"})
    )

    class Meta:
        model = Funcionario
        fields = [
            "nombre",
            "apellido",
            "cedula",
            "turno",
            "empresa",
            "sucursal_rel",
            "cargo",
            "sector",
            "ips",
            "bono",
            "modalidad_cobro",
            "banco",
            "tipo_cuenta",
            "numero_cuenta",
            "fecha_ingreso",
            "foto",
            "activo",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "apellido": forms.TextInput(attrs={"class": "form-control"}),
            "cedula": forms.TextInput(attrs={"class": "form-control"}),
            "turno": forms.Select(attrs={"class": "form-control"}),
            "sucursal_rel": forms.Select(attrs={"class": "form-control"}),
            "cargo": forms.Select(attrs={"class": "form-control"}),
            "sector": forms.Select(attrs={"class": "form-control"}),
            "bono": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "modalidad_cobro": forms.Select(attrs={"class": "form-control"}),
            "banco": forms.Select(attrs={"class": "form-control"}),
            "tipo_cuenta": forms.Select(attrs={"class": "form-control"}),
            "numero_cuenta": forms.TextInput(attrs={"class": "form-control"}),
            "foto": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "sucursal_rel": "Sucursal",
            "modalidad_cobro": "Modalidad de cobro",
            "tipo_cuenta": "Tipo de cuenta",
            "numero_cuenta": "Número de cuenta",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        config = ConfiguracionGeneral.obtener()

        self.fields["turno"].queryset = Turno.objects.filter(activo=True).order_by("nombre")
        self.fields["turno"].required = False
        self.fields["turno"].empty_label = "Seleccionar turno"

        self.fields["empresa"].required = False
        self.fields["empresa"].empty_label = "Seleccionar empresa"

        self.fields["sucursal_rel"].required = False
        self.fields["sucursal_rel"].queryset = Sucursal.objects.none()
        self.fields["sucursal_rel"].empty_label = "Seleccionar sucursal"

        self.fields["cargo"].choices = [("", "Seleccionar cargo")] + config.cargos_choices
        self.fields["sector"].choices = [("", "Seleccionar sector")] + config.sectores_choices

        empresa_id = None

        if self.is_bound:
            empresa_id = self.data.get("empresa")
        elif self.instance.pk and self.instance.sucursal_rel:
            empresa_id = self.instance.sucursal_rel.empresa_id
            self.fields["empresa"].initial = self.instance.sucursal_rel.empresa

        if empresa_id:
            try:
                self.fields["sucursal_rel"].queryset = Sucursal.objects.filter(
                    empresa_id=empresa_id,
                    activo=True
                ).order_by("nombre")
            except (ValueError, TypeError):
                self.fields["sucursal_rel"].queryset = Sucursal.objects.none()

        if self.instance.pk:
            valor_salario = self.instance.salario_base
        else:
            valor_salario = config.salario_base_default

        self.fields["salario_base_fijo"].initial = f"{int(valor_salario):,}".replace(",", ".")

    def clean_cedula(self):
        cedula = self.cleaned_data["cedula"].strip()
        qs = Funcionario.objects.filter(cedula=cedula)

        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError("Ya existe un funcionario con esa cédula.")
        return cedula

    def clean(self):
        cleaned_data = super().clean()
        empresa = cleaned_data.get("empresa")
        sucursal_rel = cleaned_data.get("sucursal_rel")
        modalidad_cobro = cleaned_data.get("modalidad_cobro")
        banco = cleaned_data.get("banco")
        tipo_cuenta = cleaned_data.get("tipo_cuenta")
        numero_cuenta = (cleaned_data.get("numero_cuenta") or "").strip()

        if empresa and sucursal_rel and sucursal_rel.empresa_id != empresa.id:
            raise forms.ValidationError("La sucursal seleccionada no pertenece a la empresa elegida.")

        if modalidad_cobro == Funcionario.ModalidadesCobro.TRANSFERENCIA:
            if not banco or not tipo_cuenta or not numero_cuenta:
                raise forms.ValidationError(
                    "Si el funcionario cobra por transferencia, debes completar banco, tipo de cuenta y número de cuenta."
                )

        if modalidad_cobro == Funcionario.ModalidadesCobro.EFECTIVO:
            cleaned_data["banco"] = ""
            cleaned_data["tipo_cuenta"] = ""
            cleaned_data["numero_cuenta"] = ""

        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        config = ConfiguracionGeneral.obtener()

        obj.salario_base = config.salario_base_default
        obj.porcentaje_limite_deuda = config.porcentaje_limite_deuda_default

        if obj.sucursal_rel:
            obj.sucursal = obj.sucursal_rel.nombre
        else:
            obj.sucursal = ""

        if obj.modalidad_cobro == Funcionario.ModalidadesCobro.EFECTIVO:
            obj.banco = ""
            obj.tipo_cuenta = ""
            obj.numero_cuenta = ""

        if commit:
            obj.save()
            self.save_m2m()
        return obj


class DeudaForm(forms.ModelForm):
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = Deuda
        fields = [
            "funcionario",
            "tipo",
            "descripcion",
            "fecha",
            "monto_total",
            "saldo_pendiente",
            "cuota_mensual",
            "aplicar_en_nomina",
            "activa",
        ]
        widgets = {
            "funcionario": forms.Select(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-control"}),
            "descripcion": forms.TextInput(attrs={"class": "form-control"}),
            "monto_total": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "saldo_pendiente": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "cuota_mensual": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "aplicar_en_nomina": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["funcionario"].queryset = Funcionario.objects.filter(activo=True).order_by("apellido", "nombre")

    def clean(self):
        cleaned_data = super().clean()
        funcionario = cleaned_data.get("funcionario")
        monto_total = cleaned_data.get("monto_total") or 0
        saldo_pendiente = cleaned_data.get("saldo_pendiente")
        cuota_mensual = cleaned_data.get("cuota_mensual") or 0

        if saldo_pendiente is None:
            cleaned_data["saldo_pendiente"] = monto_total
            saldo_pendiente = monto_total

        if saldo_pendiente > monto_total:
            raise forms.ValidationError("El saldo pendiente no puede ser mayor al monto total.")

        if cuota_mensual < 0:
            raise forms.ValidationError("La cuota mensual no puede ser negativa.")

        if funcionario:
            deuda_actual = funcionario.total_deuda_activa
            if self.instance.pk:
                deuda_actual -= self.instance.saldo_pendiente

            deuda_proyectada = deuda_actual + saldo_pendiente
            if deuda_proyectada > funcionario.limite_deuda_monto:
                raise forms.ValidationError(
                    f"Esta deuda supera el límite configurado del funcionario. "
                    f"Límite: {funcionario.limite_deuda_monto} | "
                    f"Deuda actual: {funcionario.total_deuda_activa} | "
                    f"Deuda proyectada: {deuda_proyectada}"
                )

        return cleaned_data


class MarcacionForm(forms.Form):
    cedula = forms.CharField(
        label="Cédula",
        max_length=30,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-lg",
            "placeholder": "Ingresa la cédula del funcionario"
        })
    )


class PermisoLicenciaForm(forms.ModelForm):
    fecha_desde = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    fecha_hasta = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = PermisoLicencia
        fields = [
            "funcionario",
            "tipo",
            "fecha_desde",
            "fecha_hasta",
            "motivo",
            "adjunto",
            "estado",
            "observacion",
        ]
        widgets = {
            "funcionario": forms.Select(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-control"}),
            "motivo": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "adjunto": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "estado": forms.Select(attrs={"class": "form-control"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["funcionario"].queryset = Funcionario.objects.filter(activo=True).order_by("apellido", "nombre")

    def clean(self):
        cleaned_data = super().clean()
        fecha_desde = cleaned_data.get("fecha_desde")
        fecha_hasta = cleaned_data.get("fecha_hasta")

        if fecha_desde and fecha_hasta and fecha_hasta < fecha_desde:
            raise forms.ValidationError("La fecha hasta no puede ser menor que la fecha desde.")

        return cleaned_data


class VacacionForm(forms.ModelForm):
    fecha_desde = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    fecha_hasta = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = Vacacion
        fields = [
            "funcionario",
            "fecha_desde",
            "fecha_hasta",
            "dias_solicitados",
            "estado",
            "observacion",
        ]
        widgets = {
            "funcionario": forms.Select(attrs={"class": "form-control"}),
            "dias_solicitados": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "estado": forms.Select(attrs={"class": "form-control"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["funcionario"].queryset = Funcionario.objects.filter(activo=True).order_by("apellido", "nombre")

    def clean(self):
        cleaned_data = super().clean()
        funcionario = cleaned_data.get("funcionario")
        fecha_desde = cleaned_data.get("fecha_desde")
        fecha_hasta = cleaned_data.get("fecha_hasta")
        dias_solicitados = cleaned_data.get("dias_solicitados")
        estado = cleaned_data.get("estado")
        hoy = timezone.localdate()

        if fecha_desde and fecha_hasta and fecha_hasta < fecha_desde:
            raise forms.ValidationError("La fecha hasta no puede ser menor que la fecha desde.")

        if fecha_desde:
            if fecha_desde.weekday() != 0:
                raise forms.ValidationError(
                    "Según la normativa laboral, las vacaciones deben iniciar un día lunes o el siguiente día hábil si el lunes fuera feriado."
                )

            diferencia = (fecha_desde - hoy).days
            if diferencia < 15:
                raise forms.ValidationError(
                    "La notificación de vacaciones debe realizarse con al menos 15 días de anticipación."
                )

        if fecha_desde and fecha_hasta and dias_solicitados:
            dias_reales = (fecha_hasta - fecha_desde).days + 1
            if dias_solicitados != dias_reales:
                raise forms.ValidationError(
                    f"Los días solicitados no coinciden con el rango seleccionado. Deben ser {dias_reales} día(s)."
                )

        if funcionario and dias_solicitados and estado == Vacacion.Estados.APROBADO:
            saldo = funcionario.saldo_vacaciones
            if self.instance.pk and self.instance.estado == Vacacion.Estados.APROBADO:
                saldo += self.instance.dias_solicitados

            if dias_solicitados > saldo:
                raise forms.ValidationError(
                    f"El funcionario no tiene saldo suficiente. Saldo actual: {saldo} día(s)."
                )

        return cleaned_data
    
class LiquidacionForm(forms.ModelForm):
    fecha_salida = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    fecha_calculo = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = Liquidacion
        fields = [
            "funcionario",
            "tipo_salida",
            "fecha_salida",
            "fecha_calculo",
            "dias_trabajados_pendientes",
            "vacaciones_causadas_pendientes_dias",
            "preaviso_dias_otorgados",
            "preaviso_cumplido",
            "descontar_preaviso",
            "otros_descuentos",
            "motivo_observacion",
        ]
        widgets = {
            "funcionario": forms.Select(attrs={"class": "form-control"}),
            "tipo_salida": forms.Select(attrs={"class": "form-control"}),
            "dias_trabajados_pendientes": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "placeholder": "Automático según fecha de salida"
            }),
            "vacaciones_causadas_pendientes_dias": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "placeholder": "0"
            }),
            "preaviso_dias_otorgados": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "placeholder": "0"
            }),
            "preaviso_cumplido": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "descontar_preaviso": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "otros_descuentos": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0",
                "placeholder": "0"
            }),
            "motivo_observacion": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Observación interna, causal o nota administrativa"
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["funcionario"].queryset = Funcionario.objects.filter(activo=True).order_by("apellido", "nombre")
        self.fields["funcionario"].empty_label = "Seleccionar funcionario"
        self.fields["tipo_salida"].choices = [("", "Seleccionar tipo de salida")] + list(Liquidacion.TiposSalida.choices)

    def clean(self):
        cleaned = super().clean()
        funcionario = cleaned.get("funcionario")
        fecha_salida = cleaned.get("fecha_salida")

        if funcionario and fecha_salida and funcionario.fecha_ingreso and fecha_salida < funcionario.fecha_ingreso:
            raise forms.ValidationError("La fecha de salida no puede ser menor a la fecha de ingreso del funcionario.")

        return cleaned
    
class DiaLibreForm(forms.ModelForm):
    class Meta:
        model = DiaLibre
        fields = [
            "funcionario",
            "empresa",
            "sucursal",
            "sector",
            "dia_semana",
            "fecha_inicio",
            "fecha_fin",
            "activo",
            "observacion",
        ]
        widgets = {
            "funcionario": forms.Select(attrs={"class": "form-control"}),
            "empresa": forms.Select(attrs={"class": "form-control"}),
            "sucursal": forms.Select(attrs={"class": "form-control"}),
            "sector": forms.TextInput(attrs={"class": "form-control", "readonly": "readonly"}),
            "dia_semana": forms.Select(attrs={"class": "form-control"}),
            "fecha_inicio": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "observacion": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["funcionario"].queryset = Funcionario.objects.filter(activo=True).order_by("apellido", "nombre")
        self.fields["empresa"].queryset = Empresa.objects.filter(activo=True).order_by("nombre")
        self.fields["empresa"].required = False
        self.fields["sucursal"].required = False
        self.fields["sucursal"].queryset = Sucursal.objects.filter(activo=True).order_by("nombre")

        if self.instance and self.instance.pk:
            self.fields["sector"].initial = self.instance.funcionario.sector
            if self.instance.funcionario.sucursal_rel:
                self.fields["empresa"].initial = self.instance.funcionario.sucursal_rel.empresa
                self.fields["sucursal"].initial = self.instance.funcionario.sucursal_rel

    def clean(self):
        cleaned = super().clean()
        funcionario = cleaned.get("funcionario")
        empresa = cleaned.get("empresa")
        sucursal = cleaned.get("sucursal")
        fecha_inicio = cleaned.get("fecha_inicio")
        fecha_fin = cleaned.get("fecha_fin")

        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio:
            raise forms.ValidationError("La fecha fin no puede ser menor que la fecha inicio.")

        if funcionario:
            if funcionario.sucursal_rel:
                empresa_real = funcionario.sucursal_rel.empresa
                sucursal_real = funcionario.sucursal_rel

                if empresa and empresa != empresa_real:
                    raise forms.ValidationError("La empresa no coincide con la del funcionario.")
                if sucursal and sucursal != sucursal_real:
                    raise forms.ValidationError("La sucursal no coincide con la del funcionario.")

                cleaned["empresa"] = empresa_real
                cleaned["sucursal"] = sucursal_real

            cleaned["sector"] = funcionario.sector or ""

        return cleaned    