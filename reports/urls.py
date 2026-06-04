from django.urls import path

from .views import reports_dashboard


urlpatterns = [
    path('', reports_dashboard, name='reports_dashboard'),
]