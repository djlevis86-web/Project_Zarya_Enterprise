from django.contrib import admin

from .models import OCRJob


@admin.register(OCRJob)
class OCRJobAdmin(admin.ModelAdmin):

    list_display = (

        "id",

        "status",

        "created_at",

        "started_at",

        "finished_at",

    )

    list_filter = (
        "status",
    )

    search_fields = (
        "file_path",
    )