from .permissions import (
    user_can_approve_invoices,
    user_can_manage_counterparties,
    user_can_process_invoices,
    user_can_upload_invoices,
    user_can_view_all_invoices,
    user_can_view_counterparties,
    user_can_view_finance_workspace,
)


def access_policy(request):
    user = request.user
    return {
        "access_policy": {
            "can_view_finance_workspace": user_can_view_finance_workspace(user),
            "can_view_all_invoices": user_can_view_all_invoices(user),
            "can_process_invoices": user_can_process_invoices(user),
            "can_approve_invoices": user_can_approve_invoices(user),
            "can_upload_invoices": user_can_upload_invoices(user),
            "can_view_counterparties": user_can_view_counterparties(user),
            "can_manage_counterparties": user_can_manage_counterparties(user),
        }
    }
