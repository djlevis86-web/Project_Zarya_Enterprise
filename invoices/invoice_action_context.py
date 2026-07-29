from __future__ import annotations

from users.permissions import user_can_process_invoices


def get_invoice_detail_action_context(
    user,
    invoice,
) -> dict[str, object]:
    """Return the visible invoice actions from existing server policy."""

    can_manage_invoice = bool(
        user.is_authenticated
        and user.is_staff
    )

    can_process_invoice = bool(
        user_can_process_invoices(
            user
        )
    )

    has_counterparty = bool(
        invoice.counterparty_id
    )

    show_counterparty_primary_action = bool(
        can_manage_invoice
        and not has_counterparty
    )

    show_counterparty_menu_action = bool(
        can_manage_invoice
        and has_counterparty
    )

    can_delete_invoice = (
        can_manage_invoice
    )

    show_action_menu = bool(
        show_counterparty_menu_action
        or can_process_invoice
        or can_delete_invoice
    )

    return {
        "can_edit_invoice": can_manage_invoice,
        (
            "show_invoice_counterparty_primary_action"
        ): show_counterparty_primary_action,
        (
            "show_invoice_counterparty_menu_action"
        ): show_counterparty_menu_action,
        (
            "can_process_invoice_ocr"
        ): can_process_invoice,
        "can_delete_invoice": can_delete_invoice,
        "show_invoice_action_bar": bool(
            can_manage_invoice
            or show_counterparty_primary_action
            or show_action_menu
        ),
        "show_invoice_action_menu": (
            show_action_menu
        ),
    }
