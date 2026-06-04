from django.db import models
from django.conf import settings


class Invoice(models.Model):

    STATUS_NEW = 'new'
    STATUS_REVIEW = 'review'
    STATUS_APPROVED = 'approved'
    STATUS_PAID = 'paid'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_NEW, 'Новый'),
        (STATUS_REVIEW, 'На проверке'),
        (STATUS_APPROVED, 'Подтвержден'),
        (STATUS_PAID, 'Оплачен'),
        (STATUS_REJECTED, 'Отклонен'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='invoices'
    )

    title = models.CharField(
        max_length=255
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    file = models.FileField(
        upload_to='invoices/'
    )

    file_hash = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True
    )

    original_filename = models.CharField(
        max_length=255,
        blank=True
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    ocr_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='OCR сумма'
    )
    
    ocr_verified = models.BooleanField(
        default=False,
        verbose_name='OCR проверен'
    )

    ocr_comment = models.TextField(
        blank=True,
        null=True,
        verbose_name='Комментарий OCR'
    )

    amount_verified = models.BooleanField(
        default=False,
        verbose_name='Сумма проверена'
    )

    ocr_text = models.TextField(
        blank=True,
        null=True
    )

    invoice_number = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    invoice_date = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    vendor = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
        verbose_name='Статус'
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.title} ({self.user.username})"
   
    @property
    def is_pdf(self):
        return self.file.name.lower().endswith('.pdf')