from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from .forms import LoginForm, ProfileForm

from .forms import (
    LoginForm,
    UserSettingsForm
)
from invoices.models import Invoice
from django.utils import timezone


def login_view(request):

    if request.user.is_authenticated:
        return redirect('dashboard')

    form = LoginForm(
        data=request.POST or None
    )

    if request.method == 'POST':

        if form.is_valid():

            login(
                request,
                form.get_user()
            )

            return redirect(
                'dashboard'
            )

    return render(
        request,
        'login.html',
        {
            'form': form
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
        status='new'
    ).count()

    review_count = invoices.filter(
        status='review'
    ).count()

    paid_count = invoices.filter(
        status='paid'
    ).count()

    approved_count = invoices.filter(
        status='approved'
    ).count()

    latest_invoices = invoices.order_by(
        '-created_at'
    )[:5]

    attention_items = [
        {
            'label': 'Новые счета',
            'value': new_count,
            'hint': 'Ожидают OCR и первичной проверки',
            'url_name': 'invoice_list',
        },
        {
            'label': 'На проверке',
            'value': review_count,
            'hint': 'Нужно принять решение по счетам',
            'url_name': 'invoice_list',
        },
        {
            'label': 'Готово к оплате',
            'value': approved_count,
            'hint': 'Можно включать в платежный реестр',
            'url_name': 'payment_registry',
        },
    ]

    context = {

        'total_count': total_count,

        'month_count': month_count,

        'new_count': new_count,

        'review_count': review_count,

        'approved_count': approved_count,

        'latest_invoices': latest_invoices,

        'paid_count': paid_count,

        'attention_items': attention_items,
    }

    return render(
        request,
        'dashboard.html',
        context
    )


@login_required
def profile(request):

    if request.method == 'POST':

        form = ProfileForm(
            request.POST,
            instance=request.user
        )

        if form.is_valid():

            form.save()

            return redirect('profile')

    else:

        form = ProfileForm(
            instance=request.user
        )

    return render(
        request,
        'profile.html',
        {
            'form': form
        }
    )


def logout_view(request):

    logout(request)

    return redirect(
        'login'
    )
