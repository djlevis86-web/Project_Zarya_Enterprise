from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .models import Invoice


@dataclass(frozen=True)
class ReadinessIssue:
    code: str
    message: str
    field: str = ""


@dataclass(frozen=True)
class DocumentReadinessResult:
    blockers: tuple[ReadinessIssue, ...]
    warnings: tuple[ReadinessIssue, ...]
    next_action: str
    is_legacy_repair: bool

    @property
    def can_approve(self) -> bool:
        return not self.blockers

    @property
    def blocker_messages(self) -> list[str]:
        return [issue.message for issue in self.blockers]

    @property
    def warning_messages(self) -> list[str]:
        return [issue.message for issue in self.warnings]

    @property
    def primary_blocker(self) -> ReadinessIssue | None:
        return self.blockers[0] if self.blockers else None


@dataclass(frozen=True)
class PaymentReadinessResult:
    blockers: tuple[ReadinessIssue, ...]
    warnings: tuple[ReadinessIssue, ...]
    next_action: str
    remaining_amount: Decimal | None
    is_legacy_repair: bool

    @property
    def can_add_to_registry(self) -> bool:
        return not self.blockers

    @property
    def blocker_messages(self) -> list[str]:
        return [issue.message for issue in self.blockers]

    @property
    def warning_messages(self) -> list[str]:
        return [issue.message for issue in self.warnings]

    @property
    def primary_blocker(self) -> ReadinessIssue | None:
        return self.blockers[0] if self.blockers else None


def _decimal(value: object) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value))


def _append_once(
    issues: list[ReadinessIssue],
    issue: ReadinessIssue,
) -> None:
    if issue.code not in {item.code for item in issues}:
        issues.append(issue)


def _document_next_action(
    invoice: object,
    blockers: Iterable[ReadinessIssue],
) -> str:
    if tuple(blockers):
        return "Исправить данные документа"

    status = getattr(invoice, "status", Invoice.STATUS_NEW)
    actions = {
        Invoice.STATUS_NEW: "Принять документ в работу",
        Invoice.STATUS_IN_WORK: "Передать на согласование",
        Invoice.STATUS_ON_APPROVAL: "Утвердить документ",
        Invoice.STATUS_APPROVED: "Подготовить документ к оплате",
        Invoice.STATUS_PAID: "Просмотреть оплату",
    }
    return actions.get(status, "Проверить документ")


def evaluate_document_readiness(
    invoice: object,
) -> DocumentReadinessResult:
    blockers: list[ReadinessIssue] = []
    warnings: list[ReadinessIssue] = []

    if bool(getattr(invoice, "is_deleted", False)):
        _append_once(
            blockers,
            ReadinessIssue(
                "document_deleted",
                "Документ удалён из рабочих списков.",
            ),
        )

    amount = _decimal(getattr(invoice, "amount", None))
    if amount <= Decimal("0.00"):
        _append_once(
            blockers,
            ReadinessIssue(
                "amount_missing",
                "Не указана сумма к оплате.",
                "amount",
            ),
        )

    if not bool(getattr(invoice, "amount_verified", False)):
        _append_once(
            blockers,
            ReadinessIssue(
                "amount_unverified",
                "Сумма документа не подтверждена по оригиналу.",
                "amount",
            ),
        )

    document_type = getattr(invoice, "document_type", None)
    if document_type in (None, "", Invoice.DOCUMENT_TYPE_UNKNOWN):
        _append_once(
            blockers,
            ReadinessIssue(
                "document_type_unknown",
                "Не определён тип документа.",
                "document_type",
            ),
        )

    if not getattr(invoice, "counterparty_id", None):
        _append_once(
            blockers,
            ReadinessIssue(
                "counterparty_missing",
                "Контрагент не сопоставлен со справочником.",
                "counterparty",
            ),
        )

    if not getattr(invoice, "responsible_id", None):
        _append_once(
            blockers,
            ReadinessIssue(
                "responsible_missing",
                "Ответственный не назначен.",
                "responsible",
            ),
        )

    if not str(getattr(invoice, "invoice_number", "") or "").strip():
        _append_once(
            warnings,
            ReadinessIssue(
                "invoice_number_missing",
                "Номер документа требует проверки.",
                "invoice_number",
            ),
        )

    document_date = (
        getattr(invoice, "document_date", None)
        or getattr(invoice, "invoice_date", None)
    )
    if not document_date:
        _append_once(
            warnings,
            ReadinessIssue(
                "document_date_missing",
                "Дата документа требует проверки.",
                "document_date",
            ),
        )

    if not getattr(invoice, "planned_payment_date", None):
        _append_once(
            warnings,
            ReadinessIssue(
                "planned_payment_date_missing",
                "Не указана плановая дата оплаты.",
                "planned_payment_date",
            ),
        )

    blocker_tuple = tuple(blockers)
    is_legacy_repair = bool(
        getattr(invoice, "status", None) == Invoice.STATUS_APPROVED
        and blocker_tuple
    )

    return DocumentReadinessResult(
        blockers=blocker_tuple,
        warnings=tuple(warnings),
        next_action=_document_next_action(invoice, blocker_tuple),
        is_legacy_repair=is_legacy_repair,
    )


def evaluate_payment_readiness(
    invoice: object,
    *,
    active_registry_id: int | None = None,
    payment_summary: dict[str, object] | None = None,
) -> PaymentReadinessResult:
    blockers: list[ReadinessIssue] = []
    warnings: list[ReadinessIssue] = []

    document_result = evaluate_document_readiness(invoice)
    for issue in document_result.blockers:
        _append_once(blockers, issue)

    if active_registry_id:
        _append_once(
            blockers,
            ReadinessIssue(
                "active_registry_duplicate",
                f"Документ уже есть в реестре №{active_registry_id}.",
            ),
        )

    if getattr(invoice, "paid_at", None):
        _append_once(
            blockers,
            ReadinessIssue(
                "document_paid_at",
                "Документ уже отмечен как оплаченный.",
            ),
        )

    status = getattr(invoice, "status", None)
    if status == Invoice.STATUS_PAID:
        _append_once(
            blockers,
            ReadinessIssue(
                "document_paid_status",
                "Документ уже находится в статусе оплаты.",
            ),
        )
    elif status != Invoice.STATUS_APPROVED:
        _append_once(
            blockers,
            ReadinessIssue(
                "document_not_approved",
                "Документ должен быть утверждён перед добавлением в реестр оплаты.",
                "status",
            ),
        )

    if not getattr(invoice, "planned_payment_date", None):
        _append_once(
            blockers,
            ReadinessIssue(
                "planned_payment_date_missing",
                "Не указана плановая дата оплаты.",
                "planned_payment_date",
            ),
        )
        warnings = [
            issue for issue in warnings
            if issue.code != "planned_payment_date_missing"
        ]

    counterparty = getattr(invoice, "counterparty", None)
    if counterparty is not None:
        missing = []
        for field_name, label in (
            ("inn", "ИНН"),
            ("bank_name", "банк"),
            ("account_number", "расчётный счёт"),
            ("bik", "БИК"),
        ):
            if not str(getattr(counterparty, field_name, "") or "").strip():
                missing.append(label)
        if missing:
            _append_once(
                blockers,
                ReadinessIssue(
                    "counterparty_requisites_missing",
                    "У контрагента не заполнено: " + ", ".join(missing) + ".",
                    "counterparty",
                ),
            )

    remaining_amount: Decimal | None = None

    if payment_summary is not None:
        remaining_amount = _decimal(
            payment_summary.get(
                "remaining_amount",
                Decimal("0.00"),
            )
        )

        if remaining_amount <= Decimal("0.00"):
            _append_once(
                blockers,
                ReadinessIssue(
                    "no_payment_balance",
                    (
                        "Документ уже полностью оплачен "
                        "или имеет переплату."
                    ),
                ),
            )

    blocker_tuple = tuple(blockers)
    is_legacy_repair = (
        document_result.is_legacy_repair
    )

    return PaymentReadinessResult(
        blockers=blocker_tuple,
        warnings=tuple(warnings),
        next_action=(
            "Исправить данные перед оплатой"
            if blocker_tuple
            else "Добавить в реестр оплаты"
        ),
        remaining_amount=remaining_amount,
        is_legacy_repair=is_legacy_repair,
    )
