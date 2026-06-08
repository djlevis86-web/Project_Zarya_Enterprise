from django.urls import path

from .views import (
    system_dashboard,
    backups_list,
)

urlpatterns = [

    path(
        '',
        system_dashboard,
        name='system_dashboard'
    ),

    path(
        'backups/',
        backups_list,
        name='backups_list'
    ),

]