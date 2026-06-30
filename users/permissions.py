from functools import wraps

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied


User = get_user_model()


def user_is_admin(user):
    return (
        user.is_authenticated
        and (
            user.is_superuser
            or getattr(user, "role", None) == User.Role.ADMIN
        )
    )


def user_is_finance_director(user):
    return (
        user.is_authenticated
        and getattr(user, "role", None) == User.Role.MANAGER
    )


def user_is_invoice_uploader(user):
    return (
        user.is_authenticated
        and getattr(user, "role", None) == User.Role.USER
    )


def user_can_manage_users(user):
    return user_is_admin(user)


def user_can_access_system(user):
    return user_is_admin(user)


def user_can_view_audit_log(user):
    return user_is_admin(user)


def user_can_view_all_invoices(user):
    return (
        user_is_admin(user)
        or user_is_finance_director(user)
    )


def user_can_process_invoices(user):
    return (
        user_is_admin(user)
        or user_is_finance_director(user)
    )


def user_can_upload_invoices(user):
    return (
        user.is_authenticated
        and (
            user_is_admin(user)
            or user_is_finance_director(user)
            or user_is_invoice_uploader(user)
        )
    )


def user_can_manage_counterparties(user):
    return (
        user_is_admin(user)
        or user_is_finance_director(user)
    )


def admin_required(view_func):
    return login_required(
        user_passes_test(
            user_is_admin,
            login_url="dashboard"
        )(
            view_func
        )
    )


def system_admin_required(view_func):
    return login_required(
        user_passes_test(
            user_can_access_system,
            login_url="dashboard"
        )(
            view_func
        )
    )


def audit_admin_required(view_func):
    return login_required(
        user_passes_test(
            user_can_view_audit_log,
            login_url="dashboard"
        )(
            view_func
        )
    )

def require_user_permission(check_func, message="Нет прав для выполнения действия."):

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            if not check_func(request.user):
                raise PermissionDenied(message)

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator

