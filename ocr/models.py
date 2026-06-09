from django.db import models
from invoices.models import Invoice

class OCRJob(models.Model):

    STATUS_PENDING = "PENDING"
    STATUS_PROCESSING = "PROCESSING"
    STATUS_DONE = "DONE"
    STATUS_ERROR = "ERROR"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Ожидает"),
        (STATUS_PROCESSING, "Обработка"),
        (STATUS_DONE, "Готово"),
        (STATUS_ERROR, "Ошибка"),
    ]

    invoice_id = models.IntegerField(
        null=True,
        blank=True
    )

    file_path = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

    result_text = models.TextField(
        blank=True,
        null=True
    )

    result_json = models.JSONField(
        blank=True,
        null=True
    )

    error_text = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True
    )

    finished_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):

        return (
            f"{self.id} - {self.status}"
        )