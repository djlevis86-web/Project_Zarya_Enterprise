from django.contrib import admin

from .models import (
    Invoice,
    InvoiceUploadBatch,
    Counterparty,
    CompanyRequisites,
)

from .comment_models import InvoiceComment

admin.site.register(InvoiceComment)

@admin.register(Counterparty)
class CounterpartyAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'inn',
        'kpp',
        'source',
        'is_active',
        'bank_name',
        'bik',
        'account_number',
        'synced_at',
    )

    list_filter = (
        'source',
        'is_active',
    )

    search_fields = (
        'name',
        'full_name',
        'inn',
        'kpp',
        'external_id_1c',
    )

    readonly_fields = (
        'created_at',
        'updated_at',
        'synced_at',
    )

from .models import (
    Invoice,
    Counterparty
)

@admin.register(CompanyRequisites)
class CompanyRequisitesAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'inn',
        'kpp',
        'bank_name',
        'bik',
        'account_number',
    )

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'title',
        'user',
        'counterparty',
        'amount',
        'status',
        'invoice_number',
        'invoice_date',
        'created_at',
        'counterparty_match_status',
    )

    list_filter = (
        'status',
        'created_at',
    )

    search_fields = (
        'title',
        'description',
        'invoice_number',
        'vendor',
        'user__username',
        'counterparty_match_status',
        'counterparty_match_comment',
    )

    ordering = (
        '-created_at',
    )

    readonly_fields = (
        'ocr_text',
        'created_at',
        'updated_at',
    )

    fieldsets = (

        ('Invoice Information', {
            'fields': (
                'user',
                'title',
                'description',
                'file',
                'original_filename',
                'amount',
                'status',
            )
        }),

        ('OCR Data', {
            'fields': (
                'invoice_number',
                'invoice_date',
                'vendor',
                'counterparty',
                'ocr_text',
            )
        }),

        ('System Information', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )

@admin.register(InvoiceUploadBatch)
class InvoiceUploadBatchAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'created_at',
        'user',
        'status',
        'total_files',
        'uploaded_count',
        'duplicate_count',
        'skipped_count',
    )

    list_filter = (
        'status',
        'created_at',
        'user',
    )

    search_fields = (
        'id',
        'upload_token',
        'user__username',
    )

    readonly_fields = (
        'user',
        'upload_token',
        'total_files',
        'uploaded_count',
        'duplicate_count',
        'skipped_count',
        'duplicate_files',
        'skipped_files',
        'status',
        'created_at',
    )

    ordering = (
        '-created_at',
    )