from .models import ConfiguracionGeneral
from usuarios.multiempresa import es_admin_master


def config_general(request):
    try:
        config = ConfiguracionGeneral.obtener()
    except Exception:
        config = None

    return {
        "config_general": config
    }


def suscripcion_context(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {
            "suscripcion_sistema": None,
            "mostrar_alerta_suscripcion": False,
        }

    try:
        from .models import SuscripcionSistema

        suscripcion = SuscripcionSistema.obtener()
    except Exception:
        suscripcion = None

    mostrar = bool(
        suscripcion
        and es_admin_master(request.user)
        and (suscripcion.bloqueada or suscripcion.en_gracia or suscripcion.por_vencer)
    )

    return {
        "suscripcion_sistema": suscripcion,
        "mostrar_alerta_suscripcion": mostrar,
    }
