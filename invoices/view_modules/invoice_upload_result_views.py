from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from ..models import InvoiceUploadBatch


@login_required
def upload_result(request):

    result = request.session.get(
        'last_upload_result',
        {}
    )

    batch = None

    batch_id = result.get(
        'batch_id'
    )

    if batch_id:

        batch = (
            InvoiceUploadBatch.objects
            .filter(
                id=batch_id
            )
            .first()
        )

    return render(
        request,
        'invoices/upload_result.html',
        {
            'batch': batch,
            'uploaded_count': result.get(
                'uploaded_count',
                0
            ),
            'duplicates': result.get(
                'duplicates',
                []
            ),
            'skipped_files': result.get(
                'skipped_files',
                []
            ),
        }
    )
