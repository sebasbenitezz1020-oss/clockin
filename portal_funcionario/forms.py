from datetime import timedelta

from django import forms

from core.models import PermisoLicencia, Vacacion

from .models import (
    PortalDescargoComunicacion,
    PortalSolicitudDocumento,
    PortalSolicitudMarcacion,
    PortalSugerencia,
)


class PortalPermisoForm(forms.ModelForm):
    fecha_desde = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    fecha_hasta = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))

    class Meta:
        model = PermisoLicencia
        fields = ["tipo", "fecha_desde", "fecha_hasta", "motivo", "adjunto"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-control"}),
            "motivo": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "adjunto": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def clean(self):
        cleaned = super().clean()
        fecha_desde = cleaned.get("fecha_desde")
        fecha_hasta = cleaned.get("fecha_hasta")
        if fecha_desde and fecha_hasta and fecha_hasta < fecha_desde:
            raise forms.ValidationError("La fecha hasta no puede ser menor que la fecha desde.")
        return cleaned


class PortalVacacionForm(forms.ModelForm):
    fecha_desde = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))

    class Meta:
        model = Vacacion
        fields = ["fecha_desde", "dias_solicitados", "observacion"]
        widgets = {
            "dias_solicitados": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, funcionario=None, **kwargs):
        self.funcionario = funcionario
        super().__init__(*args, **kwargs)

    def clean_dias_solicitados(self):
        dias = self.cleaned_data["dias_solicitados"]
        if dias < 1:
            raise forms.ValidationError("Debes solicitar al menos 1 día.")
        if self.funcionario and dias > self.funcionario.saldo_vacaciones:
            raise forms.ValidationError("No tienes saldo suficiente de vacaciones.")
        return dias

    def save(self, commit=True):
        vacacion = super().save(commit=False)
        if vacacion.fecha_desde and vacacion.dias_solicitados:
            vacacion.fecha_hasta = vacacion.fecha_desde + timedelta(days=vacacion.dias_solicitados - 1)
        if commit:
            vacacion.save()
        return vacacion


class PortalSolicitudDocumentoForm(forms.ModelForm):
    class Meta:
        model = PortalSolicitudDocumento
        fields = ["tipo", "motivo"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-control"}),
            "motivo": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }


class PortalSolicitudMarcacionForm(forms.ModelForm):
    fecha = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    hora_solicitada = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
    )

    class Meta:
        model = PortalSolicitudMarcacion
        fields = ["fecha", "tipo", "hora_solicitada", "motivo", "adjunto"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-control"}),
            "motivo": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "adjunto": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class PortalGestionSolicitudDocumentoForm(forms.ModelForm):
    class Meta:
        model = PortalSolicitudDocumento
        fields = ["estado", "observacion_operador", "archivo_final"]
        widgets = {
            "estado": forms.Select(attrs={"class": "form-control"}),
            "observacion_operador": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "archivo_final": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class PortalGestionSolicitudMarcacionForm(forms.ModelForm):
    class Meta:
        model = PortalSolicitudMarcacion
        fields = ["estado", "observacion_operador"]
        widgets = {
            "estado": forms.Select(attrs={"class": "form-control"}),
            "observacion_operador": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }


class PortalGestionPermisoForm(forms.ModelForm):
    class Meta:
        model = PermisoLicencia
        fields = ["estado", "observacion"]
        widgets = {
            "estado": forms.Select(attrs={"class": "form-control"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }


class PortalGestionVacacionForm(forms.ModelForm):
    class Meta:
        model = Vacacion
        fields = ["estado", "observacion"]
        widgets = {
            "estado": forms.Select(attrs={"class": "form-control"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }


class PortalSugerenciaForm(forms.ModelForm):
    class Meta:
        model = PortalSugerencia
        fields = ["categoria", "asunto", "mensaje", "adjunto"]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-control"}),
            "asunto": forms.TextInput(attrs={"class": "form-control"}),
            "mensaje": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "adjunto": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class PortalGestionSugerenciaForm(forms.ModelForm):
    class Meta:
        model = PortalSugerencia
        fields = ["estado", "respuesta_operador"]
        widgets = {
            "estado": forms.Select(attrs={"class": "form-control"}),
            "respuesta_operador": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }


class PortalDescargoComunicacionForm(forms.ModelForm):
    class Meta:
        model = PortalDescargoComunicacion
        fields = ["mensaje", "adjunto"]
        widgets = {
            "mensaje": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "adjunto": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }
