from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import AuditLog
from .services import log_action


@receiver(user_logged_in, dispatch_uid="audit_user_logged_in")
def audit_user_logged_in(sender, request, user, **kwargs):
    log_action(
        request=request,
        user=user,
        action=AuditLog.ACTION_LOGIN,
        object_type="Auth",
        object_id=str(user.pk),
        object_repr=user.get_username(),
        message="Пользователь вошёл в систему.",
    )


@receiver(user_logged_out, dispatch_uid="audit_user_logged_out")
def audit_user_logged_out(sender, request, user, **kwargs):
    username = user.get_username() if user else ""

    log_action(
        request=request,
        user=user,
        action=AuditLog.ACTION_LOGOUT,
        object_type="Auth",
        object_id=str(user.pk) if user else "",
        object_repr=username,
        message="Пользователь вышел из системы.",
    )


@receiver(user_login_failed, dispatch_uid="audit_user_login_failed")
def audit_user_login_failed(sender, credentials, request, **kwargs):
    safe_username = ""

    if credentials:
        safe_username = credentials.get("username") or credentials.get("email") or ""

    log_action(
        request=request,
        user=None,
        action=AuditLog.ACTION_SYSTEM,
        object_type="Auth",
        object_repr=safe_username,
        message="Неудачная попытка входа.",
        metadata={
            "event": "login_failed",
            "username": safe_username,
        },
    )
