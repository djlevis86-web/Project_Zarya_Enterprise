from celery import shared_task

from django.utils import timezone

from invoices.models import Invoice

from .models import OCRJob

from .services import (
    extract_text_from_pdf,
    extract_text_from_image,
    parse_invoice_data,
)

from invoices.log_service import (
    create_invoice_log,
)


@shared_task
def process_invoice_ocr(job_id):

    job = OCRJob.objects.get(
        id=job_id
    )

    try:

        job.started_at = timezone.now()

        job.status = OCRJob.STATUS_PROCESSING

        job.save()

        file_path = job.file_path

        if file_path.lower().endswith(".pdf"):

            text = extract_text_from_pdf(
                file_path
            )

        else:

            text = extract_text_from_image(
                file_path
            )

        data = parse_invoice_data(
            text
        )

        job.result_text = text

        job.result_json = data

        invoice = Invoice.objects.filter(
            id=job.invoice_id
        ).first()

        if invoice:

            invoice.ocr_text = text

            invoice.invoice_number = data.get(
                "invoice_number"
            )

            if invoice.invoice_number:

                duplicate = Invoice.objects.filter(
                    invoice_number=invoice.invoice_number
                ).exclude(
                    id=invoice.id
                ).exists()

                if duplicate:

                    invoice.status = (
                        Invoice.STATUS_REJECTED
                    )

            invoice.invoice_date = data.get(
                "invoice_date"
            )

            invoice.vendor = data.get(
                "vendor"
            )

            amount = data.get(
                "amount"
            )

            if amount:

                try:

                    invoice.ocr_amount = float(
                        str(amount).replace(",", ".")
                    )

                    if (
                        invoice.amount
                        and float(invoice.amount)
                        == float(invoice.ocr_amount)
                    ):

                        invoice.amount_verified = True

                        invoice.ocr_verified = True

                    else:

                        invoice.amount_verified = False

                        invoice.ocr_verified = False

                except Exception:

                    pass

            invoice.save()

            create_invoice_log(
                invoice,
                invoice.user,
                "OCR обработка завершена"
            )

        job.status = OCRJob.STATUS_DONE

        job.finished_at = timezone.now()

        job.save()

    except Exception as e:

        job.status = OCRJob.STATUS_ERROR

        job.error_text = str(e)

        job.finished_at = timezone.now()

        job.save()