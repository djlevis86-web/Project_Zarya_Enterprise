from django.contrib import admin

from .models import (
    PaymentRegistry,
    PaymentRegistryItem,
    Invoice,
    InvoiceUploadBatch,
    Counterparty,
    CompanyRequisites,
    ResponsiblePerson,
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

@admin.register(ResponsiblePerson)
class ResponsiblePersonAdmin(admin.ModelAdmin):

    list_display = (
        "full_name",
        "is_active",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "full_name",
    )

    ordering = (
        "full_name",
        "id",
    )


from .models import (
    PaymentRegistry,
    PaymentRegistryItem,
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
        'responsible',
        'amount',
        'status',
        'invoice_number',
        'invoice_date',
        'created_at',
        'counterparty_match_status',
    )

    list_filter = (
        'status',
        'responsible',
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
        'responsible__full_name',
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
                'responsible',
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


class PaymentRegistryItemInline(admin.TabularInline):
    model = PaymentRegistryItem
    extra = 0
    readonly_fields = (
        "invoice",
        "amount",
        "planned_payment_date",
        "status",
        "created_at",
        "exported_at",
        "paid_at",
    )
    can_delete = False


@admin.register(PaymentRegistry)
class PaymentRegistryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "status",
        "items_count",
        "total_amount",
        "created_by",
        "created_at",
        "exported_at",
    )
    list_filter = (
        "status",
        "created_at",
        "exported_at",
    )
    search_fields = (
        "title",
        "comment",
        "created_by__username",
    )
    readonly_fields = (
        "created_at",
        "checked_at",
        "exported_at",
        "items_count",
        "total_amount",
    )
    inlines = (
        PaymentRegistryItemInline,
    )


@admin.register(PaymentRegistryItem)
class PaymentRegistryItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "registry",
        "invoice",
        "amount",
        "planned_payment_date",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "planned_payment_date",
        "created_at",
    )
    search_fields = (
        "registry__title",
        "invoice__invoice_number",
        "invoice__vendor",
        "invoice__counterparty__name",
    )

from .models import InvoicePayment


@admin.register(InvoicePayment)
class InvoicePaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "invoice",
        "amount",
        "paid_at",
        "status",
        "source",
        "payment_number",
        "created_by",
        "created_at",
    )
    list_filter = (
        "status",
        "source",
        "paid_at",
        "created_at",
    )
    search_fields = (
        "invoice__title",
        "invoice__original_filename",
        "payment_number",
        "comment",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
