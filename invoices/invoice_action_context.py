from __future__ import annotations

from .access_policy import (
    user_can_add_invoice_comment,
    user_can_approve_invoice,
    user_can_edit_invoice,
    user_can_manage_invoice_data,
)


def get_invoice_detail_action_context(
    user,
    invoice,
) -> dict[str, object]:
    """Return visible invoice actions from the central access policy."""

    can_manage_invoice = user_can_manage_invoice_data(
        user
    )
    can_edit = user_can_edit_invoice(
        user,
        invoice,
    )
    can_approve = user_can_approve_invoice(
        user,
        invoice,
    )
    can_comment = user_can_add_invoice_comment(
        user,
        invoice,
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
    can_delete_invoice = can_manage_invoice

    show_action_menu = bool(
        show_counterparty_menu_action
        or can_manage_invoice
        or can_delete_invoice
    )

    return {
        "can_edit_invoice": can_edit,
        "can_approve_invoice": can_approve,
        "can_add_invoice_comment": can_comment,
        (
            "show_invoice_counterparty_primary_action"
        ): show_counterparty_primary_action,
        (
            "show_invoice_counterparty_menu_action"
        ): show_counterparty_menu_action,
        (
            "can_process_invoice_ocr"
        ): can_manage_invoice,
        "can_delete_invoice": can_delete_invoice,
        "show_invoice_action_bar": bool(
            can_edit
            or can_approve
            or show_counterparty_primary_action
            or show_action_menu
        ),
        "show_invoice_action_menu": (
            show_action_menu
        ),
    }
