from django import forms
from .models import (
    Empresa,
    Sucursal,
    Funcionario,
    Turno,
    Deuda,
    PermisoLicencia,
    Vacacion,
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
    hora_entrada = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"})
    )
    hora_salida = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"})
    )
    hora_inicio_almuerzo = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"})
    )
    hora_fin_almuerzo = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"})
    )

    class Meta:
        model = Turno
        fields = [
            "nombre",
            "hora_entrada",
            "hora_salida",
            "usa_almuerzo",
            "hora_inicio_almuerzo",
            "hora_fin_almuerzo",
            "tolerancia_minutos",
            "activo",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "usa_almuerzo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "tolerancia_minutos": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        usa_almuerzo = cleaned_data.get("usa_almuerzo")
        hora_inicio_almuerzo = cleaned_data.get("hora_inicio_almuerzo")
        hora_fin_almuerzo = cleaned_data.get("hora_fin_almuerzo")

        if usa_almuerzo and (not hora_inicio_almuerzo or not hora_fin_almuerzo):
            raise forms.ValidationError(
                "Si el turno usa almuerzo, debes completar hora inicio y fin de almuerzo."
            )

        return cleaned_data


class FuncionarioForm(forms.ModelForm):
    empresa = forms.ModelChoiceField(
        queryset=Empresa.objects.filter(activo=True).order_by("nombre"),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"})
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
            "salario_base",
            "bono",
            "porcentaje_limite_deuda",
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
            "cargo": forms.TextInput(attrs={"class": "form-control"}),
            "sector": forms.TextInput(attrs={"class": "form-control"}),
            "salario_base": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "bono": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "porcentaje_limite_deuda": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "modalidad_cobro": forms.Select(attrs={"class": "form-control"}),
            "banco": forms.Select(attrs={"class": "form-control"}),
            "tipo_cuenta": forms.Select(attrs={"class": "form-control"}),
            "numero_cuenta": forms.TextInput(attrs={"class": "form-control"}),
            "foto": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "sucursal_rel": "Sucursal",
            "porcentaje_limite_deuda": "Límite de deuda (%)",
            "modalidad_cobro": "Modalidad de cobro",
            "tipo_cuenta": "Tipo de cuenta",
            "numero_cuenta": "Número de cuenta",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["turno"].queryset = Turno.objects.filter(activo=True).order_by("nombre")
        self.fields["turno"].required = False
        self.fields["turno"].empty_label = "Seleccionar turno"

        self.fields["empresa"].required = False
        self.fields["empresa"].empty_label = "Seleccionar empresa"

        self.fields["sucursal_rel"].required = False
        self.fields["sucursal_rel"].queryset = Sucursal.objects.none()
        self.fields["sucursal_rel"].empty_label = "Seleccionar sucursal"

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

        if fecha_desde and fecha_hasta and fecha_hasta < fecha_desde:
            raise forms.ValidationError("La fecha hasta no puede ser menor que la fecha desde.")

        if funcionario and dias_solicitados and estado == Vacacion.Estados.APROBADO:
            saldo = funcionario.saldo_vacaciones
            if self.instance.pk and self.instance.estado == Vacacion.Estados.APROBADO:
                saldo += self.instance.dias_solicitados

            if dias_solicitados > saldo:
                raise forms.ValidationError(
                    f"El funcionario no tiene saldo suficiente. Saldo actual: {saldo} día(s)."
                )

        return cleaned_data