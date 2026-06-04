from django.contrib import admin

from .comment_models import InvoiceComment

admin.site.register(InvoiceComment)

from .models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'title',
        'user',
        'amount',
        'status',
        'invoice_number',
        'invoice_date',
        'created_at',
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