from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model

from .models import AuditLog


def get_client_ip(request) -> str | None:
    if request is None:
        return None

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def log_action(
    *,
    request=None,
    user=None,
    action: str,
    obj: Any = None,
    object_type: str = "",
    object_id: str = "",
    object_repr: str = "",
    message: str = "",
    metadata: dict | None = None,
) -> AuditLog:
    if user is None and request is not None:
        user = getattr(request, "user", None)

    if user is not None and not getattr(user, "is_authenticated", False):
        user = None

    if obj is not None:
        object_type = object_type or obj.__class__.__name__
        object_id = object_id or str(getattr(obj, "pk", "") or "")
        object_repr = object_repr or str(obj)

    user_agent = ""

    if request is not None:
        user_agent = request.META.get("HTTP_USER_AGENT", "")

    return AuditLog.objects.create(
        user=user,
        action=action,
        object_type=object_type,
        object_id=object_id,
        object_repr=object_repr[:255],
        message=message,
        ip_address=get_client_ip(request),
        user_agent=user_agent,
        metadata=metadata or {},
    )
