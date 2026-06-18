from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_VIEW = "view"
    ACTION_LOGIN = "login"
    ACTION_LOGOUT = "logout"
    ACTION_UPLOAD = "upload"
    ACTION_OCR = "ocr"
    ACTION_PAYMENT = "payment"
    ACTION_BACKUP = "backup"
    ACTION_SYSTEM = "system"

    ACTION_CHOICES = (
        (ACTION_CREATE, "Создание"),
        (ACTION_UPDATE, "Изменение"),
        (ACTION_DELETE, "Удаление"),
        (ACTION_VIEW, "Просмотр"),
        (ACTION_LOGIN, "Вход"),
        (ACTION_LOGOUT, "Выход"),
        (ACTION_UPLOAD, "Загрузка"),
        (ACTION_OCR, "OCR"),
        (ACTION_PAYMENT, "Оплата"),
        (ACTION_BACKUP, "Бэкап"),
        (ACTION_SYSTEM, "Система"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="Пользователь",
    )

    action = models.CharField(
        max_length=32,
        choices=ACTION_CHOICES,
        db_index=True,
        verbose_name="Действие",
    )

    object_type = models.CharField(
        max_length=120,
        blank=True,
        db_index=True,
        verbose_name="Тип объекта",
    )

    object_id = models.CharField(
        max_length=120,
        blank=True,
        db_index=True,
        verbose_name="ID объекта",
    )

    object_repr = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Объект",
    )

    message = models.TextField(
        blank=True,
        verbose_name="Описание",
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP-адрес",
    )

    user_agent = models.TextField(
        blank=True,
        verbose_name="User-Agent",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Метаданные",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Дата события",
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Журнал действия"
        verbose_name_plural = "Журнал действий"
        indexes = (
            models.Index(fields=("action", "created_at")),
            models.Index(fields=("object_type", "object_id")),
            models.Index(fields=("user", "created_at")),
        )

    def __str__(self):
        username = self.user.username if self.user else "system"
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} · {username} · {self.action}"
