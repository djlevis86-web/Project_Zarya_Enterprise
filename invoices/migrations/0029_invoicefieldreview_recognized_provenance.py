# Generated for Project Zarya D3 semantic evidence provenance.

from decimal import Decimal, InvalidOperation

from django.db import migrations, models


def _money(value):
    if value is None:
        return ""
    try:
        return format(Decimal(str(value)).quantize(Decimal("0.01")), ".2f")
    except (InvalidOperation, TypeError, ValueError):
        return str(value or "").strip()


def classify_existing_review_sources(apps, schema_editor):
    InvoiceFieldReview = apps.get_model("invoices", "InvoiceFieldReview")

    queryset = InvoiceFieldReview.objects.select_related("invoice").iterator(
        chunk_size=500
    )
    pending = []
    for review in queryset:
        raw = str(review.recognized_value or "").strip()
        source = "unknown"
        if raw:
            if review.field_name == "amount":
                ocr_amount = _money(review.invoice.ocr_amount)
                source = "legacy_ocr" if ocr_amount and raw == ocr_amount else "legacy_current"
            elif raw != str(review.current_value or "").strip():
                source = "legacy_ocr"
            else:
                source = "legacy_current"

        review.recognized_source = source
        review.recognized_at = None
        pending.append(review)
        if len(pending) >= 1000:
            InvoiceFieldReview.objects.bulk_update(
                pending,
                ("recognized_source", "recognized_at"),
                batch_size=1000,
            )
            pending = []

    if pending:
        InvoiceFieldReview.objects.bulk_update(
            pending,
            ("recognized_source", "recognized_at"),
            batch_size=1000,
        )


def preserve_source_values_on_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0028_invoicefieldreview"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoicefieldreview",
            name="recognized_source",
            field=models.CharField(
                choices=[
                    ("unknown", "Источник не подтверждён"),
                    ("ocr", "Распознавание документа"),
                    (
                        "legacy_ocr",
                        "Распознавание до фиксации источника",
                    ),
                    (
                        "legacy_current",
                        "Перенесено из текущих данных",
                    ),
                ],
                db_index=True,
                default="unknown",
                max_length=32,
                verbose_name="Источник распознанного значения",
            ),
        ),
        migrations.AddField(
            model_name="invoicefieldreview",
            name="recognized_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Когда получено распознанное значение",
            ),
        ),
        migrations.RunPython(
            classify_existing_review_sources,
            preserve_source_values_on_reverse,
        ),
    ]
