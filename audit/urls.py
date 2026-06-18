from django.urls import path

from . import views

app_name = "audit"

urlpatterns = [
    path("", views.audit_log_list, name="audit_log_list"),
    path("export.csv", views.audit_log_export_csv, name="audit_log_export_csv"),
]
