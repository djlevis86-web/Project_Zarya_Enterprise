from django import template

from invoices.payment_services import get_invoice_payment_summary


register = template.Library()


@register.simple_tag
def invoice_payment_summary(invoice):
    return get_invoice_payment_summary(invoice)


@register.simple_tag
def invoice_paid_amount(invoice):
    return get_invoice_payment_summary(invoice)["paid_amount"]


@register.simple_tag
def invoice_remaining_amount(invoice):
    return get_invoice_payment_summary(invoice)["remaining_amount"]


@register.simple_tag
def invoice_payment_status_label(invoice):
    return get_invoice_payment_summary(invoice)["payment_status_label"]
