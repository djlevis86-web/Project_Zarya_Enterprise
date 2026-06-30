from django.urls import path

from .views import (
    dashboard,
    login_view,
    logout_view,
    profile,
    user_admin_create,
    user_admin_edit,
    user_admin_list,
)

urlpatterns = [
    path("", login_view, name="login"),
    path("dashboard/", dashboard, name="dashboard"),
    path("profile/", profile, name="profile"),
    path("users/", user_admin_list, name="user_admin_list"),
    path("users/create/", user_admin_create, name="user_admin_create"),
    path("users/<int:user_id>/edit/", user_admin_edit, name="user_admin_edit"),
    path("logout/", logout_view, name="logout"),
]
