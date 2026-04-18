from .models import ConfiguracionGeneral


def config_general(request):
    try:
        config = ConfiguracionGeneral.obtener()
    except Exception:
        config = None

    return {
        "config_general": config
    }