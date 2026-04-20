from django import forms

from .models import Usuario

from core.models import Empresa


class UsuarioForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Contraseña",
        required=False,
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        required=False,
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )

    class Meta:
        model = Usuario
        fields = [
            "first_name",
            "last_name",
            "username",
            "email",
            "telefono",
            "rol",
            "empresa",
            "activo",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
            "rol": forms.Select(attrs={"class": "form-control"}),
            "empresa": forms.Select(attrs={"class": "form-control"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        self.es_edicion = kwargs.pop("es_edicion", False)
        super().__init__(*args, **kwargs)

        self.fields["empresa"].queryset = Empresa.objects.filter(activo=True).order_by("nombre")

        if not self.es_edicion:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
        else:
            self.fields["password1"].help_text = "Déjalo en blanco si no quieres cambiar la contraseña."
            self.fields["password2"].help_text = "Déjalo en blanco si no quieres cambiar la contraseña."

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        qs = Usuario.objects.filter(username__iexact=username)

        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError("Ya existe un usuario con ese username.")

        return username

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")

        if self.es_edicion:
            if p1 or p2:
                if p1 != p2:
                    raise forms.ValidationError("Las contraseñas no coinciden.")
        else:
            if not p1 or not p2:
                raise forms.ValidationError("Debes completar ambas contraseñas.")
            if p1 != p2:
                raise forms.ValidationError("Las contraseñas no coinciden.")

        return cleaned

    def save(self, commit=True):
        usuario = super().save(commit=False)

        password1 = self.cleaned_data.get("password1")
        if password1:
            usuario.set_password(password1)

        if commit:
            usuario.save()

        return usuario