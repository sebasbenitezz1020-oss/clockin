from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from usuarios.utils import es_admin_total

from .models import PermisoUsuario, Usuario


ACCIONES = [
    ("puede_ver", "Ver"),
    ("puede_crear", "Crear"),
    ("puede_editar", "Editar"),
    ("puede_eliminar", "Eliminar"),
    ("puede_aprobar", "Aprobar"),
    ("puede_confirmar", "Confirmar"),
    ("puede_pagar", "Pagar"),
    ("puede_anular", "Anular"),
]


@login_required
def usuarios_lista(request):
    q = request.GET.get("q", "").strip()
    if not es_admin_total(request.user):
        messages.error(request, "No tienes permiso para acceder a usuarios y permisos.")
        return redirect("dashboard")

    usuarios = Usuario.objects.all().order_by("first_name", "last_name", "username")

    if q:
        usuarios = usuarios.filter(
            username__icontains=q
        ) | Usuario.objects.filter(
            first_name__icontains=q
        ) | Usuario.objects.filter(
            last_name__icontains=q
        ) | Usuario.objects.filter(
            email__icontains=q
        )

    return render(request, "usuarios/usuarios_lista.html", {
        "usuarios": usuarios,
        "q": q,
    })


@login_required
def usuario_permisos(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if not es_admin_total(request.user):
        messages.error(request, "No tienes permiso para editar permisos.")
        return redirect("dashboard")

    modulos = list(PermisoUsuario.Modulos.choices)

    if request.method == "POST":
        for modulo_valor, modulo_label in modulos:
            permiso, _ = PermisoUsuario.objects.get_or_create(
                usuario=usuario,
                modulo=modulo_valor,
                defaults={"activo": True}
            )

            permiso.puede_ver = f"{modulo_valor}_puede_ver" in request.POST
            permiso.puede_crear = f"{modulo_valor}_puede_crear" in request.POST
            permiso.puede_editar = f"{modulo_valor}_puede_editar" in request.POST
            permiso.puede_eliminar = f"{modulo_valor}_puede_eliminar" in request.POST
            permiso.puede_aprobar = f"{modulo_valor}_puede_aprobar" in request.POST
            permiso.puede_confirmar = f"{modulo_valor}_puede_confirmar" in request.POST
            permiso.puede_pagar = f"{modulo_valor}_puede_pagar" in request.POST
            permiso.puede_anular = f"{modulo_valor}_puede_anular" in request.POST
            permiso.activo = True
            permiso.save()

        messages.success(request, f"Permisos actualizados correctamente para {usuario.username}.")
        return redirect("usuario_permisos", pk=usuario.pk)

    permisos_existentes = {
        p.modulo: p
        for p in PermisoUsuario.objects.filter(usuario=usuario)
    }

    filas = []
    for modulo_valor, modulo_label in modulos:
        permiso = permisos_existentes.get(modulo_valor)
        filas.append({
            "modulo_valor": modulo_valor,
            "modulo_label": modulo_label,
            "puede_ver": permiso.puede_ver if permiso else False,
            "puede_crear": permiso.puede_crear if permiso else False,
            "puede_editar": permiso.puede_editar if permiso else False,
            "puede_eliminar": permiso.puede_eliminar if permiso else False,
            "puede_aprobar": permiso.puede_aprobar if permiso else False,
            "puede_confirmar": permiso.puede_confirmar if permiso else False,
            "puede_pagar": permiso.puede_pagar if permiso else False,
            "puede_anular": permiso.puede_anular if permiso else False,
        })

    return render(request, "usuarios/usuario_permisos.html", {
        "usuario_obj": usuario,
        "filas": filas,
        "acciones": ACCIONES,
    })