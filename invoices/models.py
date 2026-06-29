from django.db import models
from django.conf import settings
from django.utils import timezone


class Counterparty(models.Model):

    SOURCE_1C = '1c'
    SOURCE_MANUAL = 'manual'
    SOURCE_OCR = 'ocr'

    SOURCE_CHOICES = [
        (SOURCE_1C, '1С'),
        (SOURCE_MANUAL, 'Вручную'),
        (SOURCE_OCR, 'OCR'),
    ]

    external_id_1c = models.CharField(
        "Код / ссылка 1С",
        max_length=255,
        blank=True,
        null=True,
        db_index=True
    )

    name = models.CharField(
        "Наименование",
        max_length=255
    )

    full_name = models.CharField(
        "Полное наименование",
        max_length=500,
        blank=True,
        null=True
    )

    inn = models.CharField(
        "ИНН",
        max_length=20,
        blank=True,
        null=True,
        db_index=True
    )

    kpp = models.CharField(
        "КПП",
        max_length=20,
        blank=True,
        null=True,
        db_index=True
    )

    bank_name = models.CharField(
        "Банк",
        max_length=255,
        blank=True,
        null=True
    )

    bik = models.CharField(
        "БИК",
        max_length=20,
        blank=True,
        null=True
    )

    account_number = models.CharField(
        "Расчетный счет",
        max_length=50,
        blank=True,
        null=True
    )

    correspondent_account = models.CharField(
        "Корр. счет",
        max_length=50,
        blank=True,
        null=True
    )

    email = models.EmailField(
        blank=True,
        null=True
    )

    phone = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    source = models.CharField(
        "Источник",
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_OCR
    )

    is_active = models.BooleanField(
        "Активен",
        default=True
    )

    synced_at = models.DateTimeField(
        "Дата синхронизации",
        blank=True,
        null=True
    )

    sync_comment = models.TextField(
        "Комментарий синхронизации",
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Контрагент"
        verbose_name_plural = "Контрагенты"
        ordering = [
            'name'
        ]

    def __str__(self):
        return self.name


class CompanyRequisites(models.Model):

    name = models.CharField(
        "Наименование организации",
        max_length=255,
        default='ОАО "Заря"'
    )

    inn = models.CharField(
        "ИНН",
        max_length=20
    )

    kpp = models.CharField(
        "КПП",
        max_length=20,
        blank=True,
        null=True
    )

    bank_name = models.CharField(
        "Банк",
        max_length=255
    )

    bik = models.CharField(
        "БИК",
        max_length=20
    )

    account_number = models.CharField(
        "Расчетный счет",
        max_length=50
    )

    correspondent_account = models.CharField(
        "Корреспондентский счет",
        max_length=50,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Реквизиты организации"
        verbose_name_plural = "Реквизиты организации"

    def __str__(self):
        return self.name


class InvoiceUploadBatch(models.Model):

    STATUS_COMPLETED = 'completed'
    STATUS_PARTIAL = 'partial'
    STATUS_EMPTY = 'empty'

    STATUS_CHOICES = [
        (STATUS_COMPLETED, 'Загружено'),
        (STATUS_PARTIAL, 'Частично загружено'),
        (STATUS_EMPTY, 'Новых файлов нет'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='invoice_upload_batches',
        verbose_name='Пользователь'
    )

    upload_token = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        verbose_name='Токен загрузки'
    )

    total_files = models.PositiveIntegerField(
        default=0,
        verbose_name='Всего файлов'
    )

    uploaded_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Новых счетов'
    )

    duplicate_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Дубликатов'
    )

    skipped_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Пропущено'
    )

    duplicate_files = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Файлы-дубликаты'
    )

    skipped_files = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Пропущенные файлы'
    )

    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_EMPTY,
        db_index=True,
        verbose_name='Статус'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата загрузки'
    )

    class Meta:
        ordering = [
            '-created_at'
        ]

        verbose_name = 'Пакет загрузки счетов'
        verbose_name_plural = 'Пакеты загрузки счетов'

    def __str__(self):
        return f'Пакет загрузки #{self.id}'


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

    COUNTERPARTY_MATCH_NOT_PROCESSED = 'not_processed'
    COUNTERPARTY_MATCH_FOUND = 'found'
    COUNTERPARTY_MATCH_NOT_FOUND = 'not_found'
    COUNTERPARTY_MATCH_AMBIGUOUS = 'ambiguous'

    COUNTERPARTY_MATCH_CHOICES = [
        (COUNTERPARTY_MATCH_NOT_PROCESSED, 'Не проверялся'),
        (COUNTERPARTY_MATCH_FOUND, 'Найден'),
        (COUNTERPARTY_MATCH_NOT_FOUND, 'Не найден в 1С'),
        (COUNTERPARTY_MATCH_AMBIGUOUS, 'Найдено несколько вариантов'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='invoices'
    )

    upload_batch = models.ForeignKey(
        InvoiceUploadBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        verbose_name='Пакет загрузки'
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

    original_filename = models.CharField(
        max_length=255,
        blank=True
    )

    file_hash = models.CharField(
        max_length=64,
        blank=True,
        default='',
        db_index=True,
        verbose_name='Хэш файла'
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

    counterparty = models.ForeignKey(
        Counterparty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        verbose_name='Контрагент'
    )

    counterparty_match_status = models.CharField(
        "Статус поиска контрагента",
        max_length=30,
        choices=COUNTERPARTY_MATCH_CHOICES,
        default=COUNTERPARTY_MATCH_NOT_PROCESSED
    )

    counterparty_match_comment = models.TextField(
        "Комментарий поиска контрагента",
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
        verbose_name='Статус'
    )

    planned_payment_date = models.DateField(
        "Плановая дата оплаты",
        null=True,
        blank=True
    )

    paid_at = models.DateField(
        "Дата оплаты",
        null=True,
        blank=True
    )

    payment_priority = models.IntegerField(
        "Приоритет",
        default=3
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

    @property
    def payment_paid_amount(self):
        from decimal import Decimal
        from django.db.models import Sum

        total = (
            self.payments
            .filter(status=InvoicePayment.STATUS_POSTED)
            .aggregate(total=Sum("amount"))
            .get("total")
        )

        return total or Decimal("0.00")

    @property
    def payment_remaining_amount(self):
        from decimal import Decimal

        invoice_amount = self.amount or Decimal("0.00")
        paid_amount = self.payment_paid_amount
        remaining = invoice_amount - paid_amount

        if remaining < Decimal("0.00"):
            return Decimal("0.00")

        return remaining

    @property
    def payment_status_code(self):
        from decimal import Decimal

        invoice_amount = self.amount or Decimal("0.00")
        paid_amount = self.payment_paid_amount

        if invoice_amount <= Decimal("0.00"):
            return "no_amount"

        if paid_amount <= Decimal("0.00"):
            return "unpaid"

        if paid_amount < invoice_amount:
            return "partial"

        if paid_amount == invoice_amount:
            return "paid"

        return "overpaid"

    @property
    def payment_status_label(self):
        labels = {
            "no_amount": "Без суммы",
            "unpaid": "Не оплачен",
            "partial": "Частично оплачен",
            "paid": "Оплачен",
            "overpaid": "Переплата",
        }

        return labels.get(
            self.payment_status_code,
            "Не оплачен"
        )


class OCRJob(models.Model):

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_ERROR = 'error'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Ожидает'),
        (STATUS_PROCESSING, 'Выполняется'),
        (STATUS_DONE, 'Готово'),
        (STATUS_ERROR, 'Ошибка'),
    ]

    SOURCE_MANUAL = 'manual'
    SOURCE_SINGLE = 'single'
    SOURCE_BULK = 'bulk'
    SOURCE_UPLOAD = 'upload'

    SOURCE_CHOICES = [
        (SOURCE_MANUAL, 'Вручную'),
        (SOURCE_SINGLE, 'Карточка счета'),
        (SOURCE_BULK, 'Массовая постановка'),
        (SOURCE_UPLOAD, 'Загрузка файла'),
    ]

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='ocr_jobs',
        verbose_name='Счет'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ocr_jobs',
        verbose_name='Пользователь'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        verbose_name='Статус'
    )

    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_MANUAL,
        verbose_name='Источник'
    )

    attempts = models.PositiveIntegerField(
        default=0,
        verbose_name='Попыток'
    )

    message = models.TextField(
        blank=True,
        null=True,
        verbose_name='Сообщение'
    )

    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name='Ошибка'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создано'
    )

    started_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Начато'
    )

    finished_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Завершено'
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Обновлено'
    )

    class Meta:
        ordering = [
            '-created_at'
        ]

        verbose_name = 'OCR задача'
        verbose_name_plural = 'OCR задачи'

        indexes = [
            models.Index(
                fields=[
                    'status',
                    'created_at',
                ]
            ),
        ]

    def __str__(self):
        return f'OCR задача #{self.id} для счета #{self.invoice_id}'


class PaymentRegistry(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_CHECKED = "checked"
    STATUS_EXPORTED = "exported"
    STATUS_PARTIALLY_PAID = "partially_paid"
    STATUS_PAID = "paid"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Черновик"),
        (STATUS_CHECKED, "Проверен"),
        (STATUS_EXPORTED, "Выгружен"),
        (STATUS_PARTIALLY_PAID, "Частично оплачен"),
        (STATUS_PAID, "Оплачен"),
        (STATUS_CANCELLED, "Отменён"),
    )

    title = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Название реестра",
    )

    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
        verbose_name="Статус",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payment_registries",
        verbose_name="Создал",
    )

    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checked_payment_registries",
        verbose_name="Проверил",
    )

    exported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exported_payment_registries",
        verbose_name="Выгрузил",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Дата создания",
    )

    checked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата проверки",
    )

    exported_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата выгрузки",
    )

    items_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Количество счетов",
    )

    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name="Сумма реестра",
    )

    comment = models.TextField(
        blank=True,
        verbose_name="Комментарий",
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Реестр оплаты"
        verbose_name_plural = "Реестры оплаты"
        indexes = (
            models.Index(fields=("status", "created_at")),
            models.Index(fields=("created_by", "created_at")),
        )

        permissions = (
            (
                "can_manage_payment_registry",
                "Может управлять реестрами оплаты",
            ),
            (
                "can_check_payment_registry",
                "Может проверять реестры оплаты",
            ),
            (
                "can_export_payment_registry",
                "Может выгружать реестры оплаты",
            ),
            (
                "can_mark_payment_registry_paid",
                "Может отмечать реестры оплаты оплаченными",
            ),
            (
                "can_cancel_payment_registry",
                "Может отменять реестры оплаты",
            ),
        )

    def __str__(self):
        if self.title:
            return self.title

        return f"Реестр оплаты №{self.pk or 'новый'}"


class PaymentRegistryItem(models.Model):
    STATUS_ADDED = "added"
    STATUS_EXPORTED = "exported"
    STATUS_PAID = "paid"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_ADDED, "Добавлен"),
        (STATUS_EXPORTED, "Выгружен"),
        (STATUS_PAID, "Оплачен"),
        (STATUS_CANCELLED, "Отменён"),
    )

    registry = models.ForeignKey(
        PaymentRegistry,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Реестр",
    )

    invoice = models.ForeignKey(
        "Invoice",
        on_delete=models.PROTECT,
        related_name="payment_registry_items",
        verbose_name="Счёт",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name="Сумма",
    )

    planned_payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Плановая дата оплаты",
    )

    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_ADDED,
        db_index=True,
        verbose_name="Статус строки",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата добавления",
    )

    exported_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата выгрузки",
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата оплаты",
    )

    comment = models.TextField(
        blank=True,
        verbose_name="Комментарий",
    )

    class Meta:
        ordering = ("planned_payment_date", "invoice_id")
        verbose_name = "Строка реестра оплаты"
        verbose_name_plural = "Строки реестра оплаты"
        constraints = (
            models.UniqueConstraint(
                fields=("registry", "invoice"),
                name="unique_invoice_in_payment_registry",
            ),
        )
        indexes = (
            models.Index(fields=("registry", "status")),
            models.Index(fields=("invoice", "status")),
            models.Index(fields=("planned_payment_date",)),
        )

    def __str__(self):
        return f"{self.registry} · счёт #{self.invoice_id}"

class InvoicePayment(models.Model):
    STATUS_POSTED = "posted"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_POSTED, "Проведён"),
        (STATUS_CANCELLED, "Отменён"),
    )

    SOURCE_MANUAL = "manual"
    SOURCE_REGISTRY = "registry"

    SOURCE_CHOICES = (
        (SOURCE_MANUAL, "Ручная оплата"),
        (SOURCE_REGISTRY, "Реестр оплаты"),
    )

    invoice = models.ForeignKey(
        "Invoice",
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="Счёт",
    )

    registry_item = models.ForeignKey(
        "PaymentRegistryItem",
        on_delete=models.SET_NULL,
        related_name="payments",
        null=True,
        blank=True,
        verbose_name="Строка реестра оплаты",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_POSTED,
        verbose_name="Статус",
    )

    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_MANUAL,
        verbose_name="Источник",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Сумма оплаты",
    )

    paid_at = models.DateField(
        default=timezone.localdate,
        verbose_name="Дата оплаты",
    )

    payment_number = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="Номер платёжного документа",
    )

    comment = models.TextField(
        blank=True,
        verbose_name="Комментарий",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_invoice_payments",
        null=True,
        blank=True,
        verbose_name="Кто внёс",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создано",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Обновлено",
    )

    class Meta:
        verbose_name = "Платёж по счёту"
        verbose_name_plural = "Платежи по счетам"
        ordering = ("-paid_at", "-created_at")
        indexes = (
            models.Index(fields=("invoice", "status")),
            models.Index(fields=("paid_at", "status")),
            models.Index(fields=("registry_item", "status")),
        )

    def __str__(self):
        return f"{self.invoice} — {self.amount}"
