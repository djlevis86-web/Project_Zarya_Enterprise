from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    """
    Авторизация по e-mail и паролю.

    Поле формы Django называется username, но пользователь вводит e-mail.
    Username оставляем как техническое поле, чтобы не ломать существующую БД.
    """

    def authenticate(
        self,
        request,
        username=None,
        password=None,
        **kwargs
    ):

        login_value = username or kwargs.get("email")

        if not login_value or not password:
            return None

        UserModel = get_user_model()

        try:
            user = UserModel.objects.get(
                Q(email__iexact=login_value)
                |
                Q(username__iexact=login_value)
            )

        except UserModel.DoesNotExist:
            UserModel().set_password(password)
            return None

        except UserModel.MultipleObjectsReturned:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
