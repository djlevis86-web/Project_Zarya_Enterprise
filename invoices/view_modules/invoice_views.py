import hashlib
import traceback
import uuid

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from audit.models import AuditLog
from audit.services import log_action

from ..comment_forms import InvoiceCommentForm
from ..comment_models import InvoiceComment
from ..forms import (
    InvoiceEditForm,
    InvoiceForm,
    InvoicePaymentForm,
)
from ..log_service import create_invoice_log
from ..models import Invoice, InvoicePayment, InvoiceUploadBatch
from ..ocr_processing_service import (
    apply_ocr_identity_to_invoice,
    get_duplicate_invoice_by_ocr_identity,
    read_and_parse_invoice_file,
)
from ..ocr_verification_service import (
    apply_ocr_amount_to_invoice,
    sync_invoice_amount_verification,
)
from ..payment_registry_services import get_active_registry_items_for_invoice
from ..payment_services import get_invoice_payment_summary
from .payment_registry_helpers import (
    PAYMENT_STATUS_FILTER_CHOICES,
    apply_payment_status_filter,
)






from .invoice_upload_views import (
    calculate_uploaded_file_hash,
    create_upload_token,
    get_latest_upload_batches_for_user,
    render_upload_invoice_form,
    upload_invoice,
)

from .invoice_upload_batch_views import (
    upload_batch_detail,
    upload_batches,
)

from .invoice_upload_result_views import (
    upload_result,
)

from .invoice_status_comment_views import (
    add_comment,
    change_invoice_status,
)

from .invoice_detail_views import (
    invoice_detail,
)


from .invoice_list_views import (
    invoice_list,
)

from .invoice_edit_views import (
    edit_invoice,
)
