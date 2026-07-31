# Generated for Project Zarya D1 persistent document field review domain.

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


FIELD_NAMES = (
    "amount",
    "invoice_number",
    "document_date",
    "vendor",
)


def _money(value):
    if value is None:
        return ""
    try:
        return format(Decimal(str(value)).quantize(Decimal("0.01")), ".2f")
    except (InvalidOperation, TypeError, ValueError):
        return str(value).strip()


def _date_value(invoice):
    value = invoice.document_date or invoice.invoice_date
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value or "").strip()


def populate_field_reviews(apps, schema_editor):
    Invoice = apps.get_model("invoices", "Invoice")
    InvoiceFieldReview = apps.get_model(
        "invoices",
        "InvoiceFieldReview",
    )

    pending = []
    queryset = Invoice.objects.all().iterator(chunk_size=500)
    for invoice in queryset:
        current_values = {
            "amount": _money(invoice.amount),
            "invoice_number": str(invoice.invoice_number or "").strip(),
            "document_date": _date_value(invoice),
            "vendor": str(invoice.vendor or "").strip(),
        }
        recognized_values = dict(current_values)
        recognized_values["amount"] = _money(invoice.ocr_amount)

        for field_name in FIELD_NAMES:
            is_confirmed = bool(
                field_name == "amount"
                and invoice.amount_verified
                and current_values[field_name]
            )
            pending.append(
                InvoiceFieldReview(
                    invoice_id=invoice.pk,
                    field_name=field_name,
                    recognized_value=recognized_values[field_name],
                    current_value=current_values[field_name],
                    confirmed_value=(
                        current_values[field_name]
                        if is_confirmed
                        else ""
                    ),
                    is_confirmed=is_confirmed,
                    confirmed_at=(
                        invoice.updated_at
                        if is_confirmed
                        else None
                    ),
                )
            )

        if len(pending) >= 2000:
            InvoiceFieldReview.objects.bulk_create(
                pending,
                batch_size=2000,
            )
            pending = []

    if pending:
        InvoiceFieldReview.objects.bulk_create(
            pending,
            batch_size=2000,
        )


def preserve_field_reviews_on_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("invoices", "0027_add_responsible_person"),
    ]

    operations = [
        migrations.CreateModel(
            name="InvoiceFieldReview",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "field_name",
                    models.CharField(
                        choices=[
                            ("amount", "Сумма"),
                            ("invoice_number", "Номер документа"),
                            ("document_date", "Дата документа"),
                            ("vendor", "Поставщик"),
                        ],
                        db_index=True,
                        max_length=32,
                        verbose_name="Поле",
                    ),
                ),
                (
                    "recognized_value",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="Распознанное значение",
                    ),
                ),
                (
                    "current_value",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="Текущее значение",
                    ),
                ),
                (
                    "confirmed_value",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="Подтверждённое значение",
                    ),
                ),
                (
                    "is_confirmed",
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        verbose_name="Подтверждено",
                    ),
                ),
                (
                    "confirmed_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Когда подтверждено",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name="Создано",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                        verbose_name="Обновлено",
                    ),
                ),
                (
                    "confirmed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="confirmed_invoice_fields",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Кем подтверждено",
                    ),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="field_reviews",
                        to="invoices.invoice",
                        verbose_name="Документ",
                    ),
                ),
            ],
            options={
                "verbose_name": "Проверка поля документа",
                "verbose_name_plural": "Проверки полей документов",
                "ordering": ("invoice_id", "field_name"),
            },
        ),
        migrations.AddConstraint(
            model_name="invoicefieldreview",
            constraint=models.UniqueConstraint(
                fields=("invoice", "field_name"),
                name="unique_invoice_field_review",
            ),
        ),
        migrations.RunPython(
            populate_field_reviews,
            preserve_field_reviews_on_reverse,
        ),
    ]
