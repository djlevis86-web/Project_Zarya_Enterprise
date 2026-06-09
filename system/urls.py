from django.urls import path

from .views import (
    system_dashboard,
    backups_list,
    create_backup,
    download_backup,
    delete_backup,
    versions_page,
    updates_page,
    maintenance_page,
)

urlpatterns = [

    path(
        "",
        system_dashboard,
        name="system_dashboard"
    ),

    path(
        "backups/",
        backups_list,
        name="backups_list"
    ),

    path(
        "create-backup/",
        create_backup,
        name="create_backup"
    ),

    path(
        "backups/download/<str:filename>/",
        download_backup,
        name="download_backup"
    ),

    path(
        "backups/delete/<str:filename>/",
        delete_backup,
        name="delete_backup"
    ),
    path(
        "versions/",
        versions_page,
        name="versions_page"
    ),
    
    path(
        "updates/",
        updates_page,
        name="updates_page"
    ),
    
    path(
        "maintenance/",
        maintenance_page,
        name="maintenance_page"
    ),

]