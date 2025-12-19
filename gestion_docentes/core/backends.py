from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class DniOrUsernameBackend(ModelBackend):
    """
    Backend de autenticación personalizado que permite a los usuarios
    iniciar sesión utilizando su nombre de usuario o su número de DNI.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        try:
            # Busca un usuario que coincida con el nombre de usuario (insensible a mayúsculas) o el DNI.
            # El campo 'username' se busca con 'iexact' para ser case-insensitive.
            # El campo 'dni' se busca con 'exact' porque los DNI son numéricos y no tienen mayúsculas/minúsculas.
            user = UserModel.objects.get(Q(username__iexact=username) | Q(dni=username))
        except UserModel.DoesNotExist:
            # Si no se encuentra ningún usuario, la autenticación falla.
            return None
        except ValueError:
            # Si el input no es un DNI válido (ej. contiene letras y no es un username),
            # puede lanzar un ValueError al comparar con el campo DNI.
            # En este caso, solo intentamos por username.
            try:
                user = UserModel.objects.get(username__iexact=username)
            except UserModel.DoesNotExist:
                return None

        # Verifica la contraseña del usuario encontrado.
        if user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
