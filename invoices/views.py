"""Facade for invoice app views.

View implementations live in invoices.view_modules.*.
This module re-exports only URL-facing view callables.
"""

from .view_modules.counterparty_assignment_views import (
    invoice_assign_counterparty,
)

from .view_modules.counterparty_import_views import (
    counterparties_missing_requisites,
    import_counterparties_1c,
    rematch_counterparties_1c,
)

from .view_modules.counterparty_unmatched_views import (
    export_unmatched_counterparties_excel,
    unmatched_counterparties,
)

from .view_modules.counterparty_directory_views import (
    counterparty_directory,
)

from .view_modules.counterparty_detail_views import (
    counterparty_detail,
)

from .view_modules.counterparty_form_views import (
    counterparty_create,
    counterparty_edit,
)

from .view_modules.invoice_upload_views import (
    upload_invoice,
)

from .view_modules.invoice_edit_views import (
    edit_invoice,
    quick_update_invoice,
)

from .view_modules.invoice_list_views import (
    invoice_list,
)

from .view_modules.invoice_detail_views import (
    invoice_detail,
)

from .view_modules.invoice_delete_views import (
    delete_invoice,
)

from .view_modules.invoice_status_comment_views import (
    add_comment,
    change_invoice_status,
)

from .view_modules.invoice_upload_result_views import (
    upload_result,
)

from .view_modules.invoice_upload_batch_views import (
    upload_batch_detail,
    upload_batches,
)

from .view_modules.payment_views import (
    add_invoice_payment,
    cancel_invoice_payment,
)

from .view_modules.payment_registry_action_views import (
    add_to_payment_registry,
    cancel_payment_registry_view,
    check_payment_registry_view,
    mark_payment_registry_paid,
    remove_from_payment_registry_item,
)

from .view_modules.payment_registry_page_views import (
    payment_registry,
    payment_registry_detail,
    payment_registry_history,
    payment_schedule,
)

from .view_modules.payment_registry_1c_export_views import (
    export_payment_registry_1c,
    export_payment_registry_draft_1c,
)

from .view_modules.payment_registry_excel_export_views import (
    export_payment_registry_draft_excel,
    export_payment_registry_excel,
)

from .view_modules.ocr_bulk_repeat_views import (
    bulk_repeat_ocr,
)

from .view_modules.ocr_enqueue_views import (
    enqueue_ocr_jobs,
)

from .view_modules.ocr_repeat_views import (
    repeat_ocr,
)

from .view_modules.ocr_queue_views import (
    ocr_queue,
)

__all__ = (
    'invoice_list',
    'upload_invoice',
    'upload_result',
    'upload_batches',
    'upload_batch_detail',
    'invoice_detail',
    'delete_invoice',
    'add_invoice_payment',
    'cancel_invoice_payment',
    'repeat_ocr',
    'bulk_repeat_ocr',
    'enqueue_ocr_jobs',
    'ocr_queue',
    'change_invoice_status',
    'add_comment',
    'edit_invoice',
    'quick_update_invoice',
    'payment_schedule',
    'payment_registry',
    'add_to_payment_registry',
    'export_payment_registry_excel',
    'export_payment_registry_1c',
    'unmatched_counterparties',
    'export_unmatched_counterparties_excel',
    'import_counterparties_1c',
    'rematch_counterparties_1c',
    'counterparties_missing_requisites',
    'counterparty_directory',
    'counterparty_detail',
    'counterparty_create',
    'counterparty_edit',
    'invoice_assign_counterparty',
    'remove_from_payment_registry_item',
    'check_payment_registry_view',
    'export_payment_registry_draft_excel',
    'export_payment_registry_draft_1c',
    'payment_registry_history',
    'payment_registry_detail',
    'mark_payment_registry_paid',
    'cancel_payment_registry_view',
)
