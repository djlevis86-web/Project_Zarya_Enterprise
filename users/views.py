from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from invoices.models import Invoice
from invoices.presentation_services import (
    annotate_invoice_workspace,
    build_dashboard_workspace,
)
from invoices.selectors import get_visible_invoices_for_user

from .permissions import admin_required

from .forms import (
    LoginForm,
    ProfileForm,
    UserAdminCreateForm,
    UserAdminEditForm,
)

User = get_user_model()


def login_view(request):

    if request.user.is_authenticated:
        return redirect("dashboard")

    form = LoginForm(
        data=request.POST or None
    )

    if request.method == "POST":

        if form.is_valid():

            login(
                request,
                form.get_user()
            )

            return redirect(
                "dashboard"
            )

    return render(
        request,
        "login.html",
        {
            "form": form
        }
    )


@login_required

@login_required
def dashboard(request):
    invoices = list(
        annotate_invoice_workspace(
            get_visible_invoices_for_user(
                request.user
            )
        ).order_by(
            "-created_at",
            "-id",
        )
    )

    workspace = build_dashboard_workspace(
        invoices
    )

    context = {
        "dashboard_workspace": workspace,
        "total_count": workspace["total_count"],
        "new_count": sum(
            1
            for invoice in invoices
            if invoice.status == Invoice.STATUS_NEW
        ),
        "review_count": sum(
            1
            for invoice in invoices
            if invoice.status == Invoice.STATUS_IN_WORK
        ),
        "approved_count": sum(
            1
            for invoice in invoices
            if invoice.status == Invoice.STATUS_APPROVED
        ),
        "paid_count": sum(
            1
            for invoice in invoices
            if invoice.status == Invoice.STATUS_PAID
        ),
        "latest_invoices": [
            item["invoice"]
            for item in workspace["latest_documents"]
        ],
    }

    return render(
        request,
        "dashboard.html",
        context,
    )



@login_required
def profile(request):

    if request.method == "POST":

        form = ProfileForm(
            request.POST,
            instance=request.user
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                "Профиль обновлен."
            )

            return redirect("profile")

    else:

        form = ProfileForm(
            instance=request.user
        )

    return render(
        request,
        "profile.html",
        {
            "form": form
        }
    )


@admin_required
def user_admin_list(request):

    users = User.objects.order_by(
        "role",
        "last_name",
        "first_name",
        "email",
    )

    role_filter = request.GET.get(
        "role",
        ""
    )

    if role_filter:
        users = users.filter(
            role=role_filter
        )

    return render(
        request,
        "users/user_admin_list.html",
        {
            "users": users,
            "role_filter": role_filter,
            "role_choices": User.Role.choices,
        }
    )


@admin_required
def user_admin_create(request):

    if request.method == "POST":

        form = UserAdminCreateForm(
            request.POST
        )

        if form.is_valid():

            user = form.save()

            messages.success(
                request,
                f"Пользователь {user.email} создан."
            )

            return redirect(
                "user_admin_list"
            )

    else:

        form = UserAdminCreateForm(
            initial={
                "is_active": True,
                "role": User.Role.USER,
            }
        )

    return render(
        request,
        "users/user_admin_form.html",
        {
            "form": form,
            "page_title": "Новый пользователь",
            "submit_label": "Создать пользователя",
        }
    )


@admin_required
def user_admin_edit(request, user_id):

    edited_user = get_object_or_404(
        User,
        pk=user_id
    )

    if request.method == "POST":

        form = UserAdminEditForm(
            request.POST,
            instance=edited_user
        )

        if form.is_valid():

            user = form.save()

            messages.success(
                request,
                f"Пользователь {user.email} обновлен."
            )

            return redirect(
                "user_admin_list"
            )

    else:

        form = UserAdminEditForm(
            instance=edited_user
        )

    return render(
        request,
        "users/user_admin_form.html",
        {
            "form": form,
            "page_title": "Редактирование пользователя",
            "submit_label": "Сохранить пользователя",
            "edited_user": edited_user,
        }
    )


def logout_view(request):

    logout(request)

    return redirect(
        "login"
    )
