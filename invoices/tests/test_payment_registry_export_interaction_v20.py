from __future__ import annotations

import re
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from invoices.models import Counterparty
from invoices.models import Invoice
from invoices.models import PaymentRegistry
from invoices.models import ResponsiblePerson
from invoices.payment_registry_services import (
    add_invoice_to_payment_registry,
    get_or_create_draft_payment_registry,
)


_TEST_MEDIA_ROOT = tempfile.mkdtemp(
    prefix="zarya-test-media-registry-export-v20-"
)


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class PaymentRegistryExportInteractionV20Tests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(
            _TEST_MEDIA_ROOT,
            ignore_errors=True,
        )

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="registry-export-v20",
            email="registry-export-v20@example.com",
            password="pass12345",
            is_staff=True,
            is_superuser=True,
        )
        self.counterparty = Counterparty.objects.create(
            name="ООО ЭКСПОРТ V20",
            full_name="ООО ЭКСПОРТ V20",
            inn="7705551111",
            kpp="770501001",
            source=Counterparty.SOURCE_1C,
            is_active=True,
            bank_name="АО ТЕСТ БАНК",
            account_number="40702810900000000001",
            bik="044525225",
            correspondent_account="30101810400000000225",
        )
        self.responsible = ResponsiblePerson.objects.create(
            full_name="Ответственный V20",
            is_active=True,
        )

    def _registry(self, marker):
        invoice = Invoice.objects.create(
            user=self.user,
            responsible=self.responsible,
            title=f"REGISTRY-EXPORT-{marker}",
            original_filename=f"REGISTRY-EXPORT-{marker}.pdf",
            file=SimpleUploadedFile(
                f"REGISTRY-EXPORT-{marker}.pdf",
                b"%PDF-1.4\n%EOF",
                content_type="application/pdf",
            ),
            amount=Decimal("1250.00"),
            status=Invoice.STATUS_APPROVED,
            amount_verified=True,
            planned_payment_date=timezone.localdate(),
            counterparty=self.counterparty,
            vendor=self.counterparty.name,
            counterparty_match_status=(
                Invoice.COUNTERPARTY_MATCH_FOUND
            ),
        )
        registry, _created = (
            get_or_create_draft_payment_registry(
                self.user
            )
        )
        item, errors, _warnings = (
            add_invoice_to_payment_registry(
                invoice,
                registry,
            )
        )
        self.assertIsNotNone(item)
        self.assertEqual(errors, [])

        registry.status = PaymentRegistry.STATUS_DRAFT
        registry.exported_by = None
        registry.exported_at = None
        registry.save(
            update_fields=(
                "status",
                "exported_by",
                "exported_at",
            )
        )
        registry.refresh_from_db()
        return registry

    def test_export_partial_uses_post_csrf_and_financial_modals(self):
        base = Path(settings.BASE_DIR)
        partial = (
            base
            / "templates/invoices/components/"
            / "payment_registry_export_controls.html"
        ).read_text(encoding="utf-8-sig")

        for route_name in (
            "export_payment_registry_draft_excel",
            "export_payment_registry_draft_1c",
        ):
            with self.subTest(route_name=route_name):
                self.assertIn(route_name, partial)

        self.assertEqual(
            partial.count('method="post"'),
            2,
        )
        self.assertEqual(
            partial.count("{% csrf_token %}"),
            2,
        )
        self.assertEqual(
            partial.count("data-registry-export-form"),
            2,
        )
        self.assertEqual(
            partial.count("data-modal-static"),
            2,
        )
        self.assertEqual(
            partial.count('href="#z-icon-close"'),
            2,
        )
        self.assertEqual(
            partial.count(
                'class="zds-icon registry-export-close-icon"'
            ),
            2,
        )
        self.assertEqual(
            partial.count(
                "registry-export-modal-header"
            ),
            2,
        )
        self.assertEqual(
            partial.count(
                "registry-export-modal-heading"
            ),
            2,
        )
        self.assertEqual(
            partial.count(
                "registry-export-modal-footer"
            ),
            2,
        )
        self.assertNotIn(
            '<path d="M7 7 17 17"></path>',
            partial,
        )

        for marker in (
            "Реестр",
            "Документов",
            "Сумма",
            "Формат",
            "Excel · XLSX",
            "1С · TXT",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, partial)

    def test_registry_templates_use_global_zds_and_no_export_get_links(self):
        base = Path(settings.BASE_DIR)
        paths = (
            "templates/invoices/payment_registry.html",
            "templates/invoices/payment_registry_detail.html",
            "templates/invoices/payment_registry_history.html",
        )

        for relative_path in paths:
            template = (
                base
                / relative_path
            ).read_text(encoding="utf-8-sig")

            with self.subTest(relative_path=relative_path):
                self.assertIn(
                    'data-zds-migrated="payment-registry-v1"',
                    template,
                )
                self.assertIn(
                    "payment_registry_export_controls.html",
                    template,
                )
                self.assertNotRegex(
                    template,
                    re.compile(
                        r'href="{%\s*url\s+'
                        r'[\'"]export_payment_registry_draft_'
                        r'(?:excel|1c)[\'"]',
                    ),
                )

        main = (
            base
            / "templates/invoices/payment_registry.html"
        ).read_text(encoding="utf-8-sig")

        for marker in (
            "registry-command-header",
            "registry-kpi-strip",
            "registry-active-grid",
            "registry-readiness-panel",
            "registry-filter-disclosure",
            "zds-table zds-table--dense",
            "zds-filter-bar",
            "zds-pagination",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, main)

    def test_history_uses_compact_seven_column_journal(self):
        base = Path(settings.BASE_DIR)
        history = (
            base
            / "templates/invoices/payment_registry_history.html"
        ).read_text(encoding="utf-8-sig")

        labels = (
            "Реестр",
            "Статус",
            "Документы",
            "Сумма",
            "Создан",
            "Последнее событие",
            "Действия",
        )

        for label in labels:
            with self.subTest(label=label):
                self.assertIn(
                    f'data-label="{label}"',
                    history,
                )

        self.assertEqual(
            history.count('data-label="'),
            len(labels),
        )
        self.assertIn(
            'colspan="7"',
            history,
        )
        self.assertIn(
            "registry-history-open",
            history,
        )
        self.assertNotIn(
            'data-label="Дата создания"',
            history,
        )
        self.assertNotIn(
            'data-label="Дата выгрузки"',
            history,
        )

    def test_registry_page_css_and_runtime_keep_owner_boundaries(self):
        base = Path(settings.BASE_DIR)
        css = (
            base
            / "static/css/pages/payment-registry.css"
        ).read_text(encoding="utf-8-sig")
        runtime = (
            base
            / "static/js/enterprise-workspace.js"
        ).read_text(encoding="utf-8-sig")
        interaction = (
            base
            / "static/js/interaction-layer-v1.js"
        ).read_text(encoding="utf-8-sig")

        for marker in (
            ".payment-registry-history-responsive",
            ".registry-history-cell--registry",
            ".registry-history-meta",
            ".registry-history-open",
            ".registry-export-close-icon",
            ".registry-export-modal-header",
            ".registry-export-modal-heading",
            ".registry-export-modal-footer",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, css)

        for forbidden in (
            ".zds-button",
            ".zds-badge",
            ".zds-table",
            ".zds-filter-bar",
            ".zds-pagination",
            "!important",
            "nth-child(",
            "rgba(",
            "overflow-x: auto",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, css)

        for marker in (
            "initRegistryExportForms",
            "submitRegistryExport",
            "new FormData(form)",
            "Content-Disposition",
            "triggerRegistryDownload",
            "pushRegistryToast",
            "window.location.reload()",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, runtime)

        self.assertIn(
            'modal.hasAttribute("data-modal-static")',
            interaction,
        )
        self.assertIn(
            '[data-export-pending="true"]',
            interaction,
        )

    def test_rendered_surfaces_expose_two_csrf_post_exports(self):
        registry = self._registry("SURFACES")
        self.client.force_login(self.user)

        urls = (
            reverse("payment_registry"),
            reverse(
                "payment_registry_detail",
                args=[registry.id],
            ),
            reverse("payment_registry_history"),
        )

        for url in urls:
            response = self.client.get(url)
            html = response.content.decode(
                "utf-8",
                errors="replace",
            )

            with self.subTest(url=url):
                self.assertEqual(
                    response.status_code,
                    200,
                )
                self.assertIn(
                    reverse(
                        "export_payment_registry_draft_excel",
                        args=[registry.id],
                    ),
                    html,
                )
                self.assertIn(
                    reverse(
                        "export_payment_registry_draft_1c",
                        args=[registry.id],
                    ),
                    html,
                )
                self.assertEqual(
                    html.count(
                        "data-registry-export-form"
                    ),
                    2,
                )
                self.assertEqual(
                    html.count(
                        "data-modal-static"
                    ),
                    2,
                )
                self.assertGreaterEqual(
                    html.count(
                        "csrfmiddlewaretoken"
                    ),
                    2,
                )

    def test_get_exports_are_rejected_without_registry_mutation(self):
        registry = self._registry("GET")
        self.client.force_login(self.user)

        for route_name in (
            "export_payment_registry_draft_excel",
            "export_payment_registry_draft_1c",
        ):
            registry.refresh_from_db()
            before_status = registry.status
            before_exported_at = registry.exported_at

            response = self.client.get(
                reverse(
                    route_name,
                    args=[registry.id],
                )
            )

            registry.refresh_from_db()

            with self.subTest(route_name=route_name):
                self.assertEqual(
                    response.status_code,
                    302,
                )
                self.assertEqual(
                    response["Location"],
                    reverse("payment_registry"),
                )
                self.assertEqual(
                    registry.status,
                    before_status,
                )
                self.assertEqual(
                    registry.exported_at,
                    before_exported_at,
                )

    def test_csrf_rejection_and_success_feedback_for_both_formats(self):
        for route_name, content_marker, message_marker in (
            (
                "export_payment_registry_draft_excel",
                "spreadsheetml.sheet",
                "Excel-файл",
            ),
            (
                "export_payment_registry_draft_1c",
                "text/plain",
                "Файл 1С",
            ),
        ):
            registry = self._registry(route_name)
            route = reverse(
                route_name,
                args=[registry.id],
            )
            csrf_client = Client(
                enforce_csrf_checks=True
            )
            csrf_client.force_login(
                self.user
            )

            rejected = csrf_client.post(route)
            registry.refresh_from_db()

            with self.subTest(
                route_name=route_name,
                phase="csrf",
            ):
                self.assertEqual(
                    rejected.status_code,
                    403,
                )
                self.assertEqual(
                    registry.status,
                    PaymentRegistry.STATUS_DRAFT,
                )

            self.client.force_login(self.user)
            response = self.client.post(route)
            registry.refresh_from_db()
            messages = [
                str(message)
                for message
                in get_messages(
                    response.wsgi_request
                )
            ]

            with self.subTest(
                route_name=route_name,
                phase="success",
            ):
                self.assertEqual(
                    response.status_code,
                    200,
                )
                self.assertIn(
                    content_marker,
                    response["Content-Type"],
                )
                self.assertEqual(
                    registry.status,
                    PaymentRegistry.STATUS_EXPORTED,
                )
                self.assertTrue(
                    any(
                        message_marker in message
                        and f"№{registry.id}" in message
                        for message in messages
                    )
                )
