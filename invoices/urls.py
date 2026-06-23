from django.urls import path

from .views import (
    invoice_list,
    upload_invoice,
    upload_result,
    upload_batches,
    upload_batch_detail,
    invoice_detail,
    repeat_ocr,
    bulk_repeat_ocr,
    enqueue_ocr_jobs,
    ocr_queue,
    change_invoice_status,
    add_comment,
    edit_invoice,
    payment_schedule,
    payment_registry,
    add_to_payment_registry,
    export_payment_registry_excel,
    export_payment_registry_1c,
    unmatched_counterparties,
    export_unmatched_counterparties_excel,
    import_counterparties_1c,
    rematch_counterparties_1c,
    counterparties_missing_requisites,
    counterparty_directory,
    counterparty_detail,
    counterparty_create,
    counterparty_edit,
    invoice_assign_counterparty,
    remove_from_payment_registry_item,
    check_payment_registry_view,
    export_payment_registry_draft_excel,
    export_payment_registry_draft_1c,
    payment_registry_history,
)


urlpatterns = [

    path(
        '',
        invoice_list,
        name='invoice_list'
    ),

    path(
        'ocr-queue/',
        ocr_queue,
        name='ocr_queue'
    ),

    path(
        'ocr-queue/enqueue/',
        enqueue_ocr_jobs,
        name='enqueue_ocr_jobs'
    ),

    path(
        'bulk-repeat-ocr/',
        bulk_repeat_ocr,
        name='bulk_repeat_ocr'
    ),

    path(
        'upload/',
        upload_invoice,
        name='upload_invoice'
    ),

    path(
        'upload-result/',
        upload_result,
        name='upload_result'
    ),

    path(
        'uploads/',
        upload_batches,
        name='upload_batches'
    ),

    path(
        'uploads/<int:batch_id>/',
        upload_batch_detail,
        name='upload_batch_detail'
    ),

    path(
        'payment-schedule/',
        payment_schedule,
        name='payment_schedule'
    ),
    path(
        'payment-registry/history/',
        payment_registry_history,
        name='payment_registry_history'
    ),

    path(
        'payment-registry/<int:registry_id>/export-excel/',
        export_payment_registry_draft_excel,
        name='export_payment_registry_draft_excel'
    ),

    path(
        'payment-registry/<int:registry_id>/export-1c/',
        export_payment_registry_draft_1c,
        name='export_payment_registry_draft_1c'
    ),

    path(
        'payment-registry/<int:registry_id>/check/',
        check_payment_registry_view,
        name='check_payment_registry'
    ),

    path(
        'payment-registry/item/<int:item_id>/remove/',
        remove_from_payment_registry_item,
        name='remove_from_payment_registry_item'
    ),


    path(
        'payment-registry/add/',
        add_to_payment_registry,
        name='add_to_payment_registry'
    ),
    path(
        'payment-registry/',
        payment_registry,
        name='payment_registry'
    ),


    path(
        'payment-registry/export-excel/',
        export_payment_registry_excel,
        name='export_payment_registry_excel'
    ),

    path(
        'payment-registry/export-1c/',
        export_payment_registry_1c,
        name='export_payment_registry_1c'
    ),

    path(
        'unmatched-counterparties/',
        unmatched_counterparties,
        name='unmatched_counterparties'
    ),

    path(
        'unmatched-counterparties/export-excel/',
        export_unmatched_counterparties_excel,
        name='export_unmatched_counterparties_excel'
    ),

    path(
        'counterparties/import-1c/',
        import_counterparties_1c,
        name='import_counterparties_1c'
    ),

    path(
        'counterparties/rematch-1c/',
        rematch_counterparties_1c,
        name='rematch_counterparties_1c'
    ),

    path(
        'counterparties/missing-requisites/',
        counterparties_missing_requisites,
        name='counterparties_missing_requisites'
    ),

    path(
        'counterparties/',
        counterparty_directory,
        name='counterparty_directory'
    ),

    path(
        'counterparties/create/',
        counterparty_create,
        name='counterparty_create'
    ),

    path(
        'counterparties/<int:counterparty_id>/',
        counterparty_detail,
        name='counterparty_detail'
    ),

    path(
        'counterparties/<int:counterparty_id>/edit/',
        counterparty_edit,
        name='counterparty_edit'
    ),

    path(
        '<int:invoice_id>/',
        invoice_detail,
        name='invoice_detail'
    ),

    path(
        '<int:invoice_id>/repeat-ocr/',
        repeat_ocr,
        name='repeat_ocr'
    ),


    path(
        '<int:invoice_id>/assign-counterparty/',
        invoice_assign_counterparty,
        name='invoice_assign_counterparty'
    ),

    path(
        '<int:invoice_id>/status/<str:status>/',
        change_invoice_status,
        name='change_invoice_status'
    ),

    path(
        '<int:invoice_id>/comment/',
        add_comment,
        name='add_comment'
    ),

    path(
        'invoice/<int:invoice_id>/edit/',
        edit_invoice,
        name='edit_invoice'
    ),

]
