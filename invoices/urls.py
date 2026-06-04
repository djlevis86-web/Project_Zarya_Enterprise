from django.urls import path

from .views import (
    invoice_list,
    upload_invoice,
    invoice_detail,
    change_invoice_status,
    add_comment,
    edit_invoice,
    upload_result
)

urlpatterns = [

    path(
        '',
        invoice_list,
        name='invoice_list'
    ),

    path(
        'upload/',
        upload_invoice,
        name='upload_invoice'
    ),

    path(
        '<int:invoice_id>/',
        invoice_detail,
        name='invoice_detail'
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

    path(
        'upload-result/',
        upload_result,
        name='upload_result'
    ),

]