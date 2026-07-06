from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from invoices.bot_report_services import read_latest_invoice_bot_report
from invoices.models import Invoice

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
def dashboard(request):

    invoices = Invoice.objects.all()

    if not request.user.is_staff:

        invoices = invoices.filter(
            user=request.user
        )

    total_count = invoices.count()

    month_start = timezone.now().replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    month_count = invoices.filter(
        created_at__gte=month_start
    ).count()

    new_count = invoices.filter(
        status="new"
    ).count()

    review_count = invoices.filter(
        status="review"
    ).count()

    paid_count = invoices.filter(
        status="paid"
    ).count()

    approved_count = invoices.filter(
        status="approved"
    ).count()

    latest_invoices = invoices.order_by(
        "-created_at"
    )[:5]

    attention_items = [
        {
            "label": "Новые документы",
            "value": new_count,
            "hint": "Ожидают OCR и первичной проверки",
            "url_name": "invoice_list",
        },
        {
            "label": "На проверке",
            "value": review_count,
            "hint": "Нужно принять решение по документам",
            "url_name": "invoice_list",
        },
        {
            "label": "Готово к оплате",
            "value": approved_count,
            "hint": "Можно включать в платежный реестр",
            "url_name": "payment_registry",
        },
    ]

    context = {
        "total_count": total_count,
        "month_count": month_count,
        "new_count": new_count,
        "review_count": review_count,
        "approved_count": approved_count,
        "latest_invoices": latest_invoices,
        "paid_count": paid_count,
        "attention_items": attention_items,
        "invoice_bot_report": read_latest_invoice_bot_report(),
    }

    return render(
        request,
        "dashboard.html",
        context
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
