from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from .models import AuditLog


def staff_required(user):
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(staff_required)
def audit_log_list(request):
    logs = AuditLog.objects.select_related("user").all()

    q = request.GET.get("q", "").strip()
    action = request.GET.get("action", "").strip()
    object_type = request.GET.get("object_type", "").strip()
    user_id = request.GET.get("user", "").strip()

    if q:
        logs = logs.filter(
            Q(user__username__icontains=q)
            | Q(object_type__icontains=q)
            | Q(object_id__icontains=q)
            | Q(object_repr__icontains=q)
            | Q(message__icontains=q)
            | Q(ip_address__icontains=q)
        )

    if action:
        logs = logs.filter(action=action)

    if object_type:
        logs = logs.filter(object_type=object_type)

    if user_id:
        logs = logs.filter(user_id=user_id)

    paginator = Paginator(logs, 30)
    page_obj = paginator.get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)

    User = get_user_model()

    context = {
        "page_obj": page_obj,
        "actions": AuditLog.ACTION_CHOICES,
        "object_types": (
            AuditLog.objects.exclude(object_type="")
            .order_by("object_type")
            .values_list("object_type", flat=True)
            .distinct()
        ),
        "users": (
            User.objects.filter(audit_logs__isnull=False)
            .distinct()
            .order_by("username")
        ),
        "filters": {
            "q": q,
            "action": action,
            "object_type": object_type,
            "user": user_id,
        },
        "querystring": params.urlencode(),
    }

    return render(request, "audit/audit_log_list.html", context)
