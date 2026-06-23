from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def user_can_manage_payment_registry(user):
    return (
        user.is_authenticated
        and (
            user.is_staff
            or user.has_perm("invoices.can_manage_payment_registry")
        )
    )


def user_can_check_payment_registry(user):
    return (
        user.is_authenticated
        and (
            user.is_staff
            or user.has_perm("invoices.can_check_payment_registry")
            or user.has_perm("invoices.can_manage_payment_registry")
        )
    )


def user_can_export_payment_registry(user):
    return (
        user.is_authenticated
        and (
            user.is_staff
            or user.has_perm("invoices.can_export_payment_registry")
            or user.has_perm("invoices.can_manage_payment_registry")
        )
    )


def user_can_mark_payment_registry_paid(user):
    return (
        user.is_authenticated
        and (
            user.is_staff
            or user.has_perm("invoices.can_mark_payment_registry_paid")
            or user.has_perm("invoices.can_manage_payment_registry")
        )
    )


def user_can_cancel_payment_registry(user):
    return (
        user.is_authenticated
        and (
            user.is_staff
            or user.has_perm("invoices.can_cancel_payment_registry")
            or user.has_perm("invoices.can_manage_payment_registry")
        )
    )


def require_payment_registry_permission(check_function, message):
    def decorator(view_function):
        @wraps(view_function)
        def wrapper(request, *args, **kwargs):
            if check_function(request.user):
                return view_function(request, *args, **kwargs)

            messages.warning(
                request,
                message,
            )

            return redirect(
                "payment_registry"
            )

        return wrapper

    return decorator

def get_payment_registry_permission_context(user):
    return {
        "can_manage_payment_registry": user_can_manage_payment_registry(user),
        "can_check_payment_registry": user_can_check_payment_registry(user),
        "can_export_payment_registry": user_can_export_payment_registry(user),
        "can_mark_payment_registry_paid": user_can_mark_payment_registry_paid(user),
        "can_cancel_payment_registry": user_can_cancel_payment_registry(user),
    }
