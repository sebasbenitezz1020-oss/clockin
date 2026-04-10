from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()


def _to_decimal(value):
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


@register.filter
def millares(value):
    """
    2500000 -> 2.500.000
    12345.67 -> 12.346
    """
    numero = _to_decimal(value)
    entero = int(round(numero))
    return f"{entero:,}".replace(",", ".")


@register.filter
def decimal_millares(value, decimales=2):
    """
    2500000.5 -> 2.500.000,50
    """
    numero = _to_decimal(value)
    try:
        decimales = int(decimales)
    except (ValueError, TypeError):
        decimales = 2

    texto = f"{numero:,.{decimales}f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return texto


@register.filter
def guaranies(value):
    """
    2500000 -> Gs. 2.500.000
    """
    return f"Gs. {millares(value)}"


@register.filter
def porcentaje(value):
    """
    30 -> 30%
    30.5 -> 30,5%
    """
    numero = _to_decimal(value)
    if numero == numero.to_integral():
        return f"{int(numero)}%"
    texto = f"{numero:.2f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",") + "%"