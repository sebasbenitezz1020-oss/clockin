from django.db import OperationalError, ProgrammingError
from django.shortcuts import redirect
from django.urls import reverse

from usuarios.multiempresa import es_admin_master


class SuscripcionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._debe_omitir(request):
            return self.get_response(request)

        try:
            from core.models import SuscripcionSistema

            suscripcion = SuscripcionSistema.obtener()
        except (OperationalError, ProgrammingError):
            return self.get_response(request)
        except Exception:
            return self.get_response(request)

        if suscripcion.bloqueada and request.user.is_authenticated and not es_admin_master(request.user):
            return redirect("suscripcion_bloqueada")

        return self.get_response(request)

    def _debe_omitir(self, request):
        path = request.path or "/"
        allowed_prefixes = (
            "/admin/",
            "/static/",
            "/media/",
            "/accounts/",
            "/login/",
            "/logout/",
            "/suscripcion/",
            "/verificar/",
        )

        if any(path.startswith(prefix) for prefix in allowed_prefixes):
            return True

        try:
            return path in {
                reverse("login"),
                reverse("logout"),
                reverse("suscripcion_bloqueada"),
                reverse("suscripcion_panel"),
            }
        except Exception:
            return False


class EmpresaActivaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._debe_omitir(request):
            return self.get_response(request)

        if request.user.is_authenticated and es_admin_master(request.user):
            if not request.session.get("empresa_activa_id"):
                return redirect("panel_global_empresas")

        return self.get_response(request)

    def _debe_omitir(self, request):
        path = request.path or "/"
        allowed_prefixes = (
            "/admin/",
            "/static/",
            "/media/",
            "/accounts/",
            "/login/",
            "/logout/",
            "/panel-global/",
            "/empresa/",
            "/empresa-activa/",
            "/empresas/",
            "/suscripcion/",
            "/verificar/",
        )
        return any(path.startswith(prefix) for prefix in allowed_prefixes)
