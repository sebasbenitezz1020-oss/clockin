from django import forms
from decimal import Decimal
from django.db.models import Q
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
    AjusteManualLiquidacion,
    DiaLibre,
    ComunicacionLaboral,
    PlanillaBancaria,
    DocumentoFuncionario,
    HistorialLaboralFuncionario,
    ConductaFuncionario,
    HistorialSalarialFuncionario,
    SuscripcionSistema,
    PagoSuscripcionSistema,
    Diarista,
    AsistenciaDiarista,
    PagoDiarista,
)

from django import forms
from django.utils import timezone
from .models import Asistencia


def _label_funcionario_buscable(funcionario):
    partes = [funcionario.nombre_completo]
    if funcionario.cedula:
        partes.append(funcionario.documento_compacto)
    if funcionario.cargo:
        partes.append(funcionario.cargo)
    if funcionario.sector:
        partes.append(funcionario.sector)
    if funcionario.sucursal_rel:
        partes.append(funcionario.sucursal_rel.nombre)
    return " · ".join(partes)


def _solo_digitos(valor):
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def _normalizar_documento(tipo_documento, numero):
    tipo = (tipo_documento or "CI").strip().upper()
    numero = (numero or "").strip()
    if tipo in ["CPF", "CNPJ"]:
        return _solo_digitos(numero)
    return numero.replace(" ", "").replace(".", "").replace("-", "")


def _digitos_repetidos(numero):
    return bool(numero) and len(set(numero)) == 1


def _cpf_valido(numero):
    cpf = _solo_digitos(numero)
    if len(cpf) != 11 or _digitos_repetidos(cpf):
        return False
    suma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = (suma * 10) % 11
    d1 = 0 if d1 == 10 else d1
    suma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = (suma * 10) % 11
    d2 = 0 if d2 == 10 else d2
    return int(cpf[9]) == d1 and int(cpf[10]) == d2


def _cnpj_valido(numero):
    cnpj = _solo_digitos(numero)
    if len(cnpj) != 14 or _digitos_repetidos(cnpj):
        return False
    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    suma = sum(int(cnpj[i]) * pesos_1[i] for i in range(12))
    resto = suma % 11
    d1 = 0 if resto < 2 else 11 - resto
    suma = sum(int(cnpj[i]) * pesos_2[i] for i in range(13))
    resto = suma % 11
    d2 = 0 if resto < 2 else 11 - resto
    return int(cnpj[12]) == d1 and int(cnpj[13]) == d2


def _validar_documento_identidad(tipo_documento, numero):
    tipo = (tipo_documento or "CI").strip().upper()
    normalizado = _normalizar_documento(tipo, numero)
    if not normalizado:
        raise forms.ValidationError("Debes ingresar el número de documento.")
    if tipo == "CPF" and not _cpf_valido(normalizado):
        raise forms.ValidationError("CPF inválido.")
    if tipo == "CNPJ" and not _cnpj_valido(normalizado):
        raise forms.ValidationError("CNPJ inválido.")
    return normalizado


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
    fecha_vencimiento_suscripcion = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={"type": "date", "class": "form-control"}
        )
    )

    class Meta:
        model = Empresa
        fields = [
            "nombre",
            "nombre_comercial",
            "razon_social",
            "ruc",
            "direccion",
            "telefono",
            "email",
            "logo",
            "color_primario",
            "color_secundario",
            "tema_visual",
            "texto_legal_pdf",
            "icl_activo",
            "permite_ajuste_manual_liquidacion",
            "activo",
            "estado",
            "plan_contratado",
            "fecha_vencimiento_suscripcion",
            "firma_gerente",
            "nombre_gerente",
            "cargo_gerente",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "nombre_comercial": forms.TextInput(attrs={"class": "form-control"}),
            "razon_social": forms.TextInput(attrs={"class": "form-control"}),
            "ruc": forms.TextInput(attrs={"class": "form-control"}),
            "direccion": forms.TextInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "color_primario": forms.TextInput(attrs={"class": "form-control", "placeholder": "#2563eb"}),
            "color_secundario": forms.TextInput(attrs={"class": "form-control", "placeholder": "#1d4ed8"}),
            "tema_visual": forms.Select(choices=[("", "Usar tema global")] + ConfiguracionGeneral.TEMAS_CHOICES, attrs={"class": "form-control"}),
            "texto_legal_pdf": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "icl_activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "permite_ajuste_manual_liquidacion": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "estado": forms.Select(attrs={"class": "form-control"}),
            "plan_contratado": forms.Select(attrs={"class": "form-control"}),
            "fecha_vencimiento_suscripcion": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "nombre_gerente": forms.TextInput(attrs={"class": "form-control"}),
            "cargo_gerente": forms.TextInput(attrs={"class": "form-control"}),
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

        # Permitir turnos nocturnos que cruzan medianoche.
        # Ejemplo: 17:00 a 01:00 del día siguiente.
        cruza_medianoche = False

        if hora_entrada and hora_salida:
            cruza_medianoche = hora_salida <= hora_entrada

        if usa_almuerzo:
            if not hora_inicio_almuerzo:
                self.add_error("hora_inicio_almuerzo", "Debes seleccionar el inicio del almuerzo.")

            if not hora_fin_almuerzo:
                self.add_error("hora_fin_almuerzo", "Debes seleccionar el fin del almuerzo.")

            if hora_entrada and hora_inicio_almuerzo and hora_inicio_almuerzo <= hora_entrada:
                self.add_error("hora_inicio_almuerzo", "El inicio de almuerzo debe ser posterior a la entrada.")

            if hora_inicio_almuerzo and hora_fin_almuerzo and hora_fin_almuerzo <= hora_inicio_almuerzo:
                self.add_error("hora_fin_almuerzo", "El fin de almuerzo debe ser mayor que el inicio de almuerzo.")

            if not cruza_medianoche:
                if hora_salida and hora_fin_almuerzo and hora_fin_almuerzo >= hora_salida:
                    self.add_error("hora_fin_almuerzo", "El fin de almuerzo debe ser anterior a la salida.")
        else:
            cleaned_data["hora_inicio_almuerzo"] = None
            cleaned_data["hora_fin_almuerzo"] = None

        return cleaned_data


class ConfiguracionGeneralForm(forms.ModelForm):
    color_primario = forms.ChoiceField(
        choices=ConfiguracionGeneral.TEMAS_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"})
    )

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
            "color_primario": "Tema de color",
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


    def _validar_lista(self, valor, nombre, minimo=0, max_item_length=None):
        items = [x.strip() for x in (valor or "").splitlines() if x.strip()]
        items_unicos = []

        for item in items:
            if item not in items_unicos:
                items_unicos.append(item)

        if len(items_unicos) > 150:
            raise forms.ValidationError(f"{nombre} tiene demasiadas opciones. Reduce la lista.")

        if max_item_length:
            largos = [item for item in items_unicos if len(item) > max_item_length]
            if largos:
                raise forms.ValidationError(
                    f"{nombre} contiene opciones de mas de {max_item_length} caracteres. "
                    f"Revisa: {largos[0]}"
                )

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

    def clean_bancos_personalizados(self):
        return self._validar_lista(
            self.cleaned_data.get("bancos_personalizados"),
            "bancos personalizados",
            minimo=0
        )

    def clean_cargos_personalizados(self):
        return self._validar_lista(
            self.cleaned_data.get("cargos_personalizados"),
            "cargos personalizados",
            minimo=0,
            max_item_length=100
        )

    def clean_sectores_personalizados(self):
        return self._validar_lista(
            self.cleaned_data.get("sectores_personalizados"),
            "sectores personalizados",
            minimo=0,
            max_item_length=100
        )


class AsistenciaDiaristaForm(forms.ModelForm):
    hora_entrada_simple = forms.TimeField(
        required=False,
        label="Hora de entrada",
        input_formats=["%H:%M"],
        widget=forms.TimeInput(format="%H:%M", attrs={"type": "time", "class": "form-control"})
    )
    hora_salida_simple = forms.TimeField(
        required=False,
        label="Hora de salida",
        input_formats=["%H:%M"],
        widget=forms.TimeInput(format="%H:%M", attrs={"type": "time", "class": "form-control"})
    )

    class Meta:
        model = AsistenciaDiarista
        fields = ["fecha", "hora_entrada_simple", "hora_salida_simple", "estado", "observacion"]
        widgets = {
            "fecha": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "estado": forms.Select(attrs={"class": "form-control"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].input_formats = ["%Y-%m-%d"]
        self.fields["fecha"].widget.format = "%Y-%m-%d"
        self.fields["estado"].choices = [
            (AsistenciaDiarista.Estados.PROGRAMADO, "Programado"),
            (AsistenciaDiarista.Estados.TRABAJADO, "Trabajado"),
            (AsistenciaDiarista.Estados.AUSENTE, "Ausente"),
            (AsistenciaDiarista.Estados.INCOMPLETO, "Incompleto"),
        ]
        if self.instance and self.instance.pk:
            if self.instance.hora_entrada:
                self.fields["hora_entrada_simple"].initial = timezone.localtime(self.instance.hora_entrada).strftime("%H:%M")
            if self.instance.hora_salida:
                self.fields["hora_salida_simple"].initial = timezone.localtime(self.instance.hora_salida).strftime("%H:%M")

    def clean(self):
        cleaned_data = super().clean()
        estado = cleaned_data.get("estado")
        entrada = cleaned_data.get("hora_entrada_simple")
        salida = cleaned_data.get("hora_salida_simple")

        if estado == AsistenciaDiarista.Estados.TRABAJADO and (not entrada or not salida):
            raise forms.ValidationError("Para marcar como trabajado debes cargar entrada y salida.")

        if estado == AsistenciaDiarista.Estados.AUSENTE and (entrada or salida):
            raise forms.ValidationError("Una ausencia no debe tener hora de entrada o salida.")

        if entrada and salida and salida <= entrada:
            raise forms.ValidationError("La salida debe ser posterior a la entrada para esta primera versión.")

        return cleaned_data


class PagoDiaristaForm(forms.ModelForm):
    marcar_pagado = forms.BooleanField(
        required=False,
        label="Marcar como pagado al generar",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )

    class Meta:
        model = PagoDiarista
        fields = [
            "fecha_pago",
            "periodo_desde",
            "periodo_hasta",
            "monto_diario_aplicado",
            "adicionales",
            "descuentos",
            "concepto_adicional",
            "motivo_ajuste",
            "observacion",
        ]
        widgets = {
            "fecha_pago": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "periodo_desde": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "periodo_hasta": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "monto_diario_aplicado": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "1"}),
            "adicionales": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "1"}),
            "descuentos": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "1"}),
            "concepto_adicional": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: movilidad, tarea extra"}),
            "motivo_ajuste": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
        labels = {
            "fecha_pago": "Fecha de pago",
            "periodo_desde": "Periodo desde",
            "periodo_hasta": "Periodo hasta",
            "monto_diario_aplicado": "Monto diario aplicado",
            "concepto_adicional": "Concepto adicional",
            "motivo_ajuste": "Motivo de ajuste",
        }

    def __init__(self, *args, **kwargs):
        self.diarista = kwargs.pop("diarista", None)
        super().__init__(*args, **kwargs)
        for field in ["fecha_pago", "periodo_desde", "periodo_hasta"]:
            self.fields[field].input_formats = ["%Y-%m-%d"]
            self.fields[field].widget.format = "%Y-%m-%d"
        if self.diarista and not self.is_bound:
            self.fields["monto_diario_aplicado"].initial = self.diarista.monto_diario_acordado
            self.fields["periodo_desde"].initial = self.diarista.fecha_inicio
            self.fields["periodo_hasta"].initial = self.diarista.fecha_fin or timezone.localdate()

    def clean(self):
        cleaned_data = super().clean()
        desde = cleaned_data.get("periodo_desde")
        hasta = cleaned_data.get("periodo_hasta")
        monto = cleaned_data.get("monto_diario_aplicado") or Decimal("0")
        adicionales = cleaned_data.get("adicionales") or Decimal("0")
        descuentos = cleaned_data.get("descuentos") or Decimal("0")

        if desde and hasta and hasta < desde:
            self.add_error("periodo_hasta", "La fecha hasta no puede ser anterior a la fecha desde.")

        if monto <= 0:
            self.add_error("monto_diario_aplicado", "El monto diario debe ser mayor a cero.")

        if adicionales < 0:
            self.add_error("adicionales", "Los adicionales no pueden ser negativos.")

        if descuentos < 0:
            self.add_error("descuentos", "Los descuentos no pueden ser negativos.")

        return cleaned_data


class DiaristaForm(forms.ModelForm):
    empresa = forms.ModelChoiceField(
        queryset=Empresa.objects.filter(activo=True).order_by("nombre"),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"})
    )

    fecha_inicio = forms.DateField(
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"})
    )
    fecha_fin = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"})
    )
    fecha_nacimiento = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = Diarista
        fields = [
            "empresa",
            "sucursal",
            "nombres",
            "apellidos",
            "cedula",
            "telefono",
            "direccion",
            "fecha_nacimiento",
            "fecha_inicio",
            "fecha_fin",
            "cantidad_dias_contratados",
            "monto_diario_acordado",
            "forma_calculo",
            "turno",
            "sector",
            "funcion_temporal",
            "observaciones",
            "estado",
            "activo",
        ]
        widgets = {
            "sucursal": forms.Select(attrs={"class": "form-control"}),
            "nombres": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Juan Carlos"}),
            "apellidos": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: López Duarte"}),
            "cedula": forms.TextInput(attrs={"class": "form-control", "placeholder": "Número de cédula"}),
            "telefono": forms.TextInput(attrs={"class": "form-control", "placeholder": "Teléfono"}),
            "direccion": forms.TextInput(attrs={"class": "form-control", "placeholder": "Dirección opcional"}),
            "cantidad_dias_contratados": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "monto_diario_acordado": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "1", "placeholder": "Ej: 150000"}),
            "forma_calculo": forms.Select(attrs={"class": "form-control"}),
            "turno": forms.Select(attrs={"class": "form-control"}),
            "sector": forms.Select(attrs={"class": "form-control"}),
            "funcion_temporal": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Ayudante de depósito"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "estado": forms.Select(attrs={"class": "form-control"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "cantidad_dias_contratados": "Cantidad de días contratados",
            "monto_diario_acordado": "Monto diario acordado",
            "forma_calculo": "Forma de cálculo",
            "funcion_temporal": "Función / tarea temporal",
        }

    def __init__(self, *args, **kwargs):
        self.empresa_activa = kwargs.pop("empresa_activa", None)
        super().__init__(*args, **kwargs)

        config = ConfiguracionGeneral.obtener()
        self.fields["sector"].choices = [("", "Seleccionar sector")] + list(config.sectores_choices)
        self.fields["empresa"].empty_label = "Seleccionar empresa"
        self.fields["sucursal"].empty_label = "Seleccionar sucursal"
        self.fields["turno"].empty_label = "Seleccionar turno"
        self.fields["sucursal"].queryset = Sucursal.objects.filter(activo=True).order_by("empresa__nombre", "nombre")
        self.fields["turno"].queryset = Turno.objects.filter(activo=True).order_by("empresa__nombre", "nombre")

        empresa_id = None
        if self.is_bound:
            empresa_id = self.data.get("empresa")
        elif self.instance.pk:
            empresa_id = self.instance.empresa_id
            self.fields["empresa"].initial = self.instance.empresa
        elif self.empresa_activa:
            empresa_id = self.empresa_activa.id
            self.fields["empresa"].initial = self.empresa_activa

        self.fields["empresa"].queryset = Empresa.objects.filter(activo=True).order_by("nombre")
        if self.empresa_activa:
            self.fields["empresa"].queryset = Empresa.objects.filter(pk=self.empresa_activa.pk)
            self.fields["empresa"].initial = self.empresa_activa

        if empresa_id:
            try:
                self.fields["sucursal"].queryset = Sucursal.objects.filter(
                    Q(empresa_id=empresa_id, activo=True) | Q(pk=getattr(self.instance, "sucursal_id", None), empresa_id=empresa_id)
                ).order_by("nombre")
                self.fields["turno"].queryset = Turno.objects.filter(
                    Q(empresa_id=empresa_id, activo=True) | Q(pk=getattr(self.instance, "turno_id", None), empresa_id=empresa_id)
                ).order_by("nombre")
            except (TypeError, ValueError):
                pass

    def clean_cedula(self):
        return (self.cleaned_data.get("cedula") or "").strip()

    def clean(self):
        cleaned_data = super().clean()
        empresa = cleaned_data.get("empresa")
        sucursal = cleaned_data.get("sucursal")
        turno = cleaned_data.get("turno")
        fecha_inicio = cleaned_data.get("fecha_inicio")
        fecha_fin = cleaned_data.get("fecha_fin")
        cantidad = cleaned_data.get("cantidad_dias_contratados") or 0
        monto = cleaned_data.get("monto_diario_acordado") or Decimal("0")

        if not empresa:
            self.add_error("empresa", "Debes seleccionar una empresa.")

        if sucursal and empresa and sucursal.empresa_id != empresa.id:
            self.add_error("sucursal", "La sucursal seleccionada no pertenece a la empresa.")

        if turno and empresa and turno.empresa_id != empresa.id:
            self.add_error("turno", "El turno seleccionado no pertenece a la empresa.")

        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio:
            self.add_error("fecha_fin", "La fecha final no puede ser anterior al inicio.")

        if fecha_inicio and not fecha_fin and cantidad:
            cleaned_data["fecha_fin"] = fecha_inicio + timezone.timedelta(days=int(cantidad) - 1)
        elif fecha_inicio and fecha_fin:
            cleaned_data["cantidad_dias_contratados"] = (fecha_fin - fecha_inicio).days + 1

        if int(cantidad or 0) < 1:
            self.add_error("cantidad_dias_contratados", "Debe ser al menos 1 día.")

        if monto <= 0:
            self.add_error("monto_diario_acordado", "El monto diario debe ser mayor a cero.")

        return cleaned_data


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
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={"type": "date", "class": "form-control"}
        )
    )

    fecha_nacimiento = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={"type": "date", "class": "form-control"}
        )
    )

    class Meta:
        model = Funcionario
        fields = [
            "nombre",
            "apellido",
            "tipo_documento",
            "cedula",
            "turno",
            "empresa",
            "sucursal_rel",
            "cargo",
            "sector",
            "ips",
            "bono",
            "usa_salario_diferenciado",
            "salario_diferenciado",
            "modalidad_cobro",
            "banco",
            "tipo_cuenta",
            "numero_cuenta",
            "fecha_ingreso",
            "foto",
            "direccion",
            "ciudad",
            "departamento",
            "telefono",
            "correo",
            "fecha_nacimiento",
            "nacionalidad",
            "estado_civil",
            "contacto_emergencia_nombre",
            "contacto_emergencia_parentesco",
            "contacto_emergencia_telefono",
            "tipo_sangre",
            "alergias",
            "enfermedad_importante",
            "medicacion_actual",
            "seguro_medico",
            "activo",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "apellido": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_documento": forms.Select(attrs={"class": "form-control", "data-document-type": "true"}),
            "cedula": forms.TextInput(attrs={"class": "form-control", "data-document-number": "true", "placeholder": "Número de documento"}),
            "turno": forms.Select(attrs={"class": "form-control"}),
            "sucursal_rel": forms.Select(attrs={"class": "form-control"}),
            "cargo": forms.Select(attrs={"class": "form-control"}),
            "sector": forms.Select(attrs={"class": "form-control"}),
            "bono": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "usa_salario_diferenciado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "salario_diferenciado": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "1",
                "min": "0",
                "placeholder": "Ej: 8000000",
            }),
            "modalidad_cobro": forms.Select(attrs={"class": "form-control"}),
            "banco": forms.Select(attrs={"class": "form-control"}),
            "tipo_cuenta": forms.Select(attrs={"class": "form-control"}),
            "numero_cuenta": forms.TextInput(attrs={"class": "form-control"}),
            "foto": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "direccion": forms.TextInput(attrs={"class": "form-control"}),
            "ciudad": forms.TextInput(attrs={"class": "form-control"}),
            "departamento": forms.TextInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
            "correo": forms.EmailInput(attrs={"class": "form-control"}),
            "nacionalidad": forms.TextInput(attrs={"class": "form-control"}),
            "estado_civil": forms.TextInput(attrs={"class": "form-control"}),

            "contacto_emergencia_nombre": forms.TextInput(attrs={"class": "form-control"}),
            "contacto_emergencia_parentesco": forms.TextInput(attrs={"class": "form-control"}),
            "contacto_emergencia_telefono": forms.TextInput(attrs={"class": "form-control"}),

            "tipo_sangre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: O+, A-, B+"}),
            "alergias": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "enfermedad_importante": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "medicacion_actual": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "seguro_medico": forms.TextInput(attrs={"class": "form-control"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "tipo_documento": "Tipo de documento",
            "cedula": "Número de documento",
            "sucursal_rel": "Sucursal",
            "usa_salario_diferenciado": "Utilizar salario diferenciado",
            "salario_diferenciado": "Salario diferenciado mensual",
            "modalidad_cobro": "Modalidad de cobro",
            "tipo_cuenta": "Tipo de cuenta",
            "numero_cuenta": "Número de cuenta",
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.empresa_activa = kwargs.pop("empresa_activa", None)
        super().__init__(*args, **kwargs)

        config = ConfiguracionGeneral.obtener()
        self._sincronizar_choices_modelo(config)
        self._original_salario_base = getattr(self.instance, "salario_base", None)
        self._original_porcentaje_limite_deuda = getattr(self.instance, "porcentaje_limite_deuda", None)

        empresa_id = None

        if self.is_bound:
            empresa_id = self.data.get("empresa")
        elif self.instance.pk and self.instance.sucursal_rel:
            empresa_id = self.instance.sucursal_rel.empresa_id
            self.fields["empresa"].initial = self.instance.sucursal_rel.empresa
        elif self.empresa_activa:
            empresa_id = self.empresa_activa.id
            self.fields["empresa"].initial = self.empresa_activa

        self.fields["empresa"].queryset = Empresa.objects.filter(activo=True).order_by("nombre")
        if self.empresa_activa:
            self.fields["empresa"].queryset = Empresa.objects.filter(pk=self.empresa_activa.pk)
            self.fields["empresa"].initial = self.empresa_activa

        turno_qs = Turno.objects.filter(activo=True)
        if empresa_id:
            turno_qs = turno_qs.filter(empresa_id=empresa_id)
        if self.instance.pk and self.instance.turno_id:
            turno_qs = Turno.objects.filter(
                Q(pk=self.instance.turno_id) | Q(pk__in=turno_qs.values("pk"))
            )
        self.fields["turno"].queryset = turno_qs.order_by("nombre")
        self.fields["turno"].required = False
        self.fields["turno"].empty_label = "Seleccionar turno"

        self.fields["empresa"].required = False
        self.fields["empresa"].empty_label = "Seleccionar empresa"
        self.fields["salario_diferenciado"].required = False

        self.fields["sucursal_rel"].required = False
        self.fields["sucursal_rel"].queryset = Sucursal.objects.none()
        self.fields["sucursal_rel"].empty_label = "Seleccionar sucursal"

        self.fields["banco"].choices = self._choices_con_actual(
            config.bancos_choices,
            getattr(self.instance, "banco", ""),
            "Seleccionar banco"
        )
        self.fields["cargo"].choices = self._choices_con_actual(
            config.cargos_choices,
            getattr(self.instance, "cargo", ""),
            "Seleccionar cargo"
        )
        self.fields["sector"].choices = self._choices_con_actual(
            config.sectores_choices,
            getattr(self.instance, "sector", ""),
            "Seleccionar sector"
        )
        self._sincronizar_choices_modelo_desde_formulario()

        if empresa_id:
            try:
                self.fields["sucursal_rel"].queryset = Sucursal.objects.filter(
                    Q(empresa_id=empresa_id, activo=True) |
                    Q(pk=getattr(self.instance, "sucursal_rel_id", None), empresa_id=empresa_id)
                ).order_by("nombre")
            except (ValueError, TypeError):
                self.fields["sucursal_rel"].queryset = Sucursal.objects.none()

        if self.instance.pk:
            valor_salario = self.instance.salario_base
        else:
            valor_salario = config.salario_base_default

        self.fields["salario_base_fijo"].initial = f"{int(valor_salario):,}".replace(",", ".")

    def _sincronizar_choices_modelo(self, config):
        self.instance._meta.get_field("banco").choices = [("", "---------")] + config.bancos_choices
        self.instance._meta.get_field("cargo").choices = config.cargos_choices
        self.instance._meta.get_field("sector").choices = config.sectores_choices
    def _sincronizar_choices_modelo_desde_formulario(self):
        self.instance._meta.get_field("banco").choices = list(self.fields["banco"].choices)
        self.instance._meta.get_field("cargo").choices = list(self.fields["cargo"].choices)
        self.instance._meta.get_field("sector").choices = list(self.fields["sector"].choices)
    def _choices_con_actual(self, choices_base, valor_actual, texto_vacio):
        choices = [("", texto_vacio)]
        valores = {""}

        for valor, etiqueta in choices_base:
            if valor not in valores:
                choices.append((valor, etiqueta))
                valores.add(valor)

        if valor_actual and valor_actual not in valores:
            choices.append((valor_actual, f"{valor_actual} (valor actual)"))

        return choices
    def clean_cedula(self):
        tipo_documento = self.cleaned_data.get("tipo_documento") or "CI"
        documento = _validar_documento_identidad(tipo_documento, self.cleaned_data.get("cedula"))
        qs = Funcionario.objects.filter(tipo_documento=tipo_documento, cedula=documento)

        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        existente = qs.first()
        if existente:
            if not existente.activo:
                raise forms.ValidationError("Ya existe un funcionario inactivo con este documento. Revisa su ficha para reincorporarlo.")
            raise forms.ValidationError("Ya existe un funcionario con este documento.")

        return documento

    def clean(self):
        cleaned_data = super().clean()
        empresa = cleaned_data.get("empresa")
        sucursal_rel = cleaned_data.get("sucursal_rel")
        modalidad_cobro = cleaned_data.get("modalidad_cobro")
        banco = cleaned_data.get("banco")
        tipo_cuenta = cleaned_data.get("tipo_cuenta")
        numero_cuenta = (cleaned_data.get("numero_cuenta") or "").strip()
        usa_salario_diferenciado = cleaned_data.get("usa_salario_diferenciado")
        salario_diferenciado = cleaned_data.get("salario_diferenciado") or Decimal("0")

        if empresa and sucursal_rel and sucursal_rel.empresa_id != empresa.id:
            raise forms.ValidationError("La sucursal seleccionada no pertenece a la empresa elegida.")

        if usa_salario_diferenciado and salario_diferenciado <= 0:
            self.add_error(
                "salario_diferenciado",
                "Debes cargar un salario diferenciado mayor a cero."
            )

        if not usa_salario_diferenciado:
            cleaned_data["salario_diferenciado"] = Decimal("0")

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

        if not obj.pk:
            obj.salario_base = config.salario_base_default
            obj.porcentaje_limite_deuda = config.porcentaje_limite_deuda_default
        else:
            obj.salario_base = self._original_salario_base
            obj.porcentaje_limite_deuda = self._original_porcentaje_limite_deuda

        if obj.usa_salario_diferenciado:
            obj.bono = Decimal("0")
        else:
            obj.salario_diferenciado = Decimal("0")

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
        label="Documento",
        max_length=30,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-lg",
            "placeholder": "Ingresa el documento del funcionario"
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
    fecha_notificacion = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={"type": "date", "class": "form-control"}
        )
    )

    class Meta:
        model = Vacacion
        fields = [
            "funcionario",
            "fecha_desde",
            "fecha_notificacion",
            "fecha_hasta",
            "dias_solicitados",
            "estado",
            "observacion",
        ]
        widgets = {
            "funcionario": forms.Select(attrs={
                "class": "form-control js-live-employee-select",
                "data-live-placeholder": "Buscar por nombre, cédula, cargo o sucursal",
            }),
            "dias_solicitados": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "estado": forms.Select(attrs={"class": "form-control"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["funcionario"].queryset = Funcionario.objects.filter(activo=True).select_related("sucursal_rel").order_by("apellido", "nombre")
        self.fields["funcionario"].label_from_instance = _label_funcionario_buscable

    def clean(self):
        cleaned_data = super().clean()
        funcionario = cleaned_data.get("funcionario")
        fecha_desde = cleaned_data.get("fecha_desde")
        fecha_hasta = cleaned_data.get("fecha_hasta")
        dias_solicitados = cleaned_data.get("dias_solicitados")
        estado = cleaned_data.get("estado")

        if fecha_desde and fecha_hasta and fecha_hasta < fecha_desde:
            raise forms.ValidationError("La fecha hasta no puede ser menor que la fecha desde.")

        if fecha_desde:
            if fecha_desde.weekday() != 0:
                raise forms.ValidationError(
                    "Según la normativa laboral, las vacaciones deben iniciar un día lunes o el siguiente día hábil si el lunes fuera feriado."
                )

            cleaned_data["fecha_notificacion"] = fecha_desde - timezone.timedelta(days=15)

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
            "funcionario": forms.Select(attrs={
                "class": "form-control js-live-employee-select",
                "data-live-placeholder": "Buscar por nombre, cédula, cargo o sucursal",
            }),
            "tipo_salida": forms.Select(attrs={"class": "form-control"}),
            "dias_trabajados_pendientes": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "placeholder": "Automático según fecha de salida",
                "readonly": "readonly",
                "data-auto-field": "true",
            }),

            "vacaciones_causadas_pendientes_dias": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "placeholder": "Automático según saldo de vacaciones",
                "readonly": "readonly",
                "data-auto-field": "true",
            }),

            "otros_descuentos": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
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
            
            "motivo_observacion": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Observación interna, causal o nota administrativa"
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["funcionario"].queryset = Funcionario.objects.filter(activo=True).select_related("sucursal_rel").order_by("apellido", "nombre")
        self.fields["funcionario"].empty_label = "Seleccionar funcionario"


class AjusteManualLiquidacionForm(forms.ModelForm):
    class Meta:
        model = AjusteManualLiquidacion
        fields = [
            "tipo",
            "concepto",
            "importe_anterior",
            "importe_nuevo",
            "motivo",
        ]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-control"}),
            "concepto": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ej: Haber extraordinario, correccion de descuento"
            }),
            "importe_anterior": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0",
            }),
            "importe_nuevo": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0",
            }),
            "motivo": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Justificacion obligatoria del ajuste"
            }),
        }
        labels = {
            "tipo": "Tipo de ajuste",
            "concepto": "Concepto",
            "importe_anterior": "Importe anterior",
            "importe_nuevo": "Importe nuevo",
            "motivo": "Motivo",
        }

    def clean_motivo(self):
        motivo = (self.cleaned_data.get("motivo") or "").strip()
        if len(motivo) < 10:
            raise forms.ValidationError("El motivo es obligatorio y debe tener al menos 10 caracteres.")
        return motivo

    def clean(self):
        cleaned_data = super().clean()
        importe_anterior = cleaned_data.get("importe_anterior") or Decimal("0")
        importe_nuevo = cleaned_data.get("importe_nuevo") or Decimal("0")

        if importe_anterior == importe_nuevo:
            raise forms.ValidationError("El importe nuevo debe ser diferente al importe anterior.")

        return cleaned_data
        self.fields["funcionario"].label_from_instance = _label_funcionario_buscable
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
class ComunicacionLaboralForm(forms.ModelForm):
    fecha_emision = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    fecha_referencia = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = ComunicacionLaboral
        fields = [
            "funcionario",
            "tipo",
            "titulo",
            "fecha_emision",
            "fecha_referencia",
            "asunto",
            "detalle_hecho",
            "contenido",
            "observacion_interna",
            "requiere_firma",
            "estado",
            "adjunto_firmado",
        ]

        widgets = {
            "funcionario": forms.Select(attrs={
                "class": "form-control js-live-employee-select",
                "data-live-placeholder": "Buscar por nombre, cédula, cargo o sucursal",
            }),
            "tipo": forms.Select(attrs={"class": "form-control"}),
            "titulo": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ej: Comunicación de ausencia injustificada"
            }),
            "asunto": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Asunto principal de la comunicación"
            }),
            "detalle_hecho": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Describe el hecho, fecha, horario, conducta o situación comunicada"
            }),
            "contenido": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 10,
                "placeholder": "Texto legal generado automáticamente. Puedes editarlo antes de guardar."
            }),
            "observacion_interna": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Observación interna de RRHH"
            }),
            "requiere_firma": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "estado": forms.Select(attrs={"class": "form-control"}),
            "adjunto_firmado": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["funcionario"].queryset = Funcionario.objects.filter(
            activo=True
        ).select_related("sucursal_rel").order_by("apellido", "nombre")

        self.fields["funcionario"].empty_label = "Seleccionar funcionario"
        self.fields["funcionario"].label_from_instance = _label_funcionario_buscable
        self.fields["tipo"].choices = [("", "Seleccionar tipo de comunicación")] + list(ComunicacionLaboral.Tipos.choices)

class PlanillaBancariaForm(forms.ModelForm):
    class Meta:
        model = PlanillaBancaria
        fields = [
            "anio",
            "mes",
            "banco",
            "formato",
            "empresa",
            "sucursal",
            "observacion",
        ]

        widgets = {
            "anio": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "2020",
            }),

            "mes": forms.Select(
                choices=[(i, f"{i:02d}") for i in range(1, 13)],
                attrs={"class": "form-control"}
            ),

            "banco": forms.Select(
                choices=[
                    ("ITAU", "Itaú"),
                    ("BASA", "Banco BASA"),
                    ("CONTINENTAL", "Continental"),
                    ("UENO", "Ueno"),
                    ("SUDAMERIS", "Sudameris"),
                    ("GNB", "Banco GNB"),
                    ("FAMILIAR", "Familiar"),
                    ("VISION", "Visión"),
                    ("GENERICA", "Genérica CSV"),
                ],
                attrs={"class": "form-control"}
            ),

            "formato": forms.Select(attrs={"class": "form-control"}),

            "empresa": forms.Select(attrs={"class": "form-control"}),

            "sucursal": forms.Select(attrs={"class": "form-control"}),

            "observacion": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
            }),
        }
class BancoHorasOtorgarForm(forms.Form):
    funcionario = forms.ModelChoiceField(
        queryset=Funcionario.objects.filter(activo=True).order_by("apellido", "nombre"),
        widget=forms.Select(attrs={"class": "form-control"})
    )

    horas = forms.IntegerField(
        min_value=1,
        max_value=8,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "min": "1",
            "max": "8",
        })
    )

    observacion = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 3,
        })
    )

class DocumentoFuncionarioForm(forms.ModelForm):
    class Meta:
        model = DocumentoFuncionario
        fields = ["tipo", "titulo", "archivo", "observacion", "activo"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-control"}),
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "archivo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class HistorialLaboralFuncionarioForm(forms.ModelForm):
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = HistorialLaboralFuncionario
        fields = ["fecha", "tipo", "titulo", "descripcion", "adjunto"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-control"}),
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "adjunto": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class ConductaFuncionarioForm(forms.ModelForm):
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = ConductaFuncionario
        fields = ["fecha", "tipo", "titulo", "descripcion", "adjunto"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-control"}),
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "adjunto": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class HistorialSalarialFuncionarioForm(forms.ModelForm):
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = HistorialSalarialFuncionario
        fields = [
            "fecha",
            "salario_anterior",
            "salario_nuevo",
            "bono_anterior",
            "bono_nuevo",
            "motivo",
            "observacion",
        ]
        widgets = {
            "salario_anterior": forms.TextInput(attrs={
                "class": "form-control money-mask"
            }),

            "salario_nuevo": forms.TextInput(attrs={
                "class": "form-control money-mask"
            }),

            "bono_anterior": forms.TextInput(attrs={
                "class": "form-control money-mask"
            }),

            "bono_nuevo": forms.TextInput(attrs={
                "class": "form-control money-mask"
            }),
            "motivo": forms.TextInput(attrs={"class": "form-control"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class SuscripcionSistemaForm(forms.ModelForm):
    fecha_inicio = forms.DateField(
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"})
    )
    fecha_proximo_pago = forms.DateField(
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"})
    )
    fecha_ultimo_pago = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = SuscripcionSistema
        fields = [
            "nombre_cliente",
            "estado",
            "fecha_inicio",
            "fecha_ultimo_pago",
            "fecha_proximo_pago",
            "dias_gracia",
            "bloquear_al_vencer",
            "contacto_pago",
            "mensaje_bloqueo",
            "observacion_interna",
        ]
        widgets = {
            "nombre_cliente": forms.TextInput(attrs={"class": "form-control"}),
            "estado": forms.Select(attrs={"class": "form-control"}),
            "dias_gracia": forms.NumberInput(attrs={"class": "form-control", "min": "0", "max": "90"}),
            "bloquear_al_vencer": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "contacto_pago": forms.TextInput(attrs={"class": "form-control"}),
            "mensaje_bloqueo": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "observacion_interna": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        fecha_inicio = cleaned.get("fecha_inicio")
        fecha_proximo_pago = cleaned.get("fecha_proximo_pago")
        dias_gracia = cleaned.get("dias_gracia")

        if fecha_inicio and fecha_proximo_pago and fecha_proximo_pago < fecha_inicio:
            raise forms.ValidationError("La fecha de proximo pago no puede ser menor que la fecha de inicio.")

        if dias_gracia is not None and dias_gracia > 90:
            raise forms.ValidationError("Los dias de gracia no pueden superar 90 dias.")

        return cleaned


class PagoSuscripcionSistemaForm(forms.ModelForm):
    fecha_pago = forms.DateField(
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = PagoSuscripcionSistema
        fields = [
            "fecha_pago",
            "meses_cubiertos",
            "monto",
            "comprobante",
            "observacion",
        ]
        widgets = {
            "meses_cubiertos": forms.Select(attrs={"class": "form-control"}),
            "monto": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "0.01"}),
            "comprobante": forms.TextInput(attrs={"class": "form-control"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean_monto(self):
        monto = self.cleaned_data.get("monto") or 0
        if monto < 0:
            raise forms.ValidationError("El monto no puede ser negativo.")
        return monto

