from .roles import ROL_PROPIETARIO, ROL_USUARIO, es_propietario


def roles_usuario(request):
    usuario = getattr(request, "user", None)
    if not getattr(usuario, "is_authenticated", False):
        return {
            "es_propietario_actual": False,
            "rol_usuario_actual": "",
        }
    propietario = es_propietario(usuario)
    return {
        "es_propietario_actual": propietario,
        "rol_usuario_actual": ROL_PROPIETARIO if propietario else ROL_USUARIO,
    }
