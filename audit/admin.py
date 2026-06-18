from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "user",
        "action",
        "object_type",
        "object_id",
        "object_repr",
        "ip_address",
    )

    list_filter = (
        "action",
        "object_type",
        "created_at",
    )

    search_fields = (
        "user__username",
        "object_type",
        "object_id",
        "object_repr",
        "message",
        "ip_address",
    )

    readonly_fields = (
        "created_at",
        "user",
        "action",
        "object_type",
        "object_id",
        "object_repr",
        "message",
        "ip_address",
        "user_agent",
        "metadata",
    )

    ordering = (
        "-created_at",
    )

    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
