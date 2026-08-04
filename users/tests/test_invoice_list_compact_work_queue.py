from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from invoices.models import Invoice


class InvoiceListCompactWorkQueueStaticTests(SimpleTestCase):
    def setUp(self):
        self.base = Path(settings.BASE_DIR)
        self.template = (
            self.base / "templates/invoices/invoice_list.html"
        ).read_text(encoding="utf-8-sig")
        self.css = (
            self.base / "static/css/pages/invoice-list.css"
        ).read_text(encoding="utf-8-sig")

    def test_compact_command_bar_uses_canonical_screen_identity(self):
        self.assertIn("invoice-list-commandbar", self.template)
        self.assertIn('<h1 class="page-title">Документы к оплате</h1>', self.template)
        self.assertIn("Рабочая очередь", self.template)
        self.assertNotIn('<h1 class="page-title">Рабочая очередь</h1>', self.template)
        self.assertIn("invoice-list-upload-label-short", self.template)
        self.assertIn("border-bottom: 1px solid var(--zds-color-border)", self.css)
        self.assertIn("background: transparent", self.css)

    def test_kpis_keep_count_and_amount_in_compact_row(self):
        for token in (
            "Всего документов",
            "Требуют внимания",
            "Готовы к реестру",
            "Просрочены",
            "invoice-list-metrics",
        ):
            self.assertIn(token, self.template)
        self.assertIn("min-height: 76px", self.css)
        self.assertIn("min-height: 72px", self.css)

    def test_primary_filter_row_and_native_advanced_filters_are_separate(self):
        self.assertIn("invoice-list-primary-filters", self.template)
        self.assertIn("invoice-list-advanced-filters", self.template)
        self.assertIn("<details", self.template)
        self.assertIn("invoice-list-advanced-filter-icon", self.template)
        self.assertIn("invoice-list-advanced-filter-chevron", self.template)
        self.assertIn("invoice-list-advanced-filter-label-closed", self.template)
        self.assertIn("invoice-list-advanced-filter-label-open", self.template)
        self.assertIn("Расширенные фильтры", self.template)
        self.assertIn("Свернуть фильтры", self.template)
        self.assertIn("grid-template-columns: auto minmax(0, 1fr) auto", self.css)
        self.assertIn("transform: rotate(180deg)", self.css)
        self.assertNotIn('content: "+"', self.css)
        self.assertNotIn('content: "−"', self.css)
        self.assertIn('name="document_date_from"', self.template)
        self.assertIn('name="document_date_to"', self.template)

    def test_quick_filters_remain_immediately_available(self):
        for label in (
            "Сегодня",
            "Просрочено",
            "На проверке",
            "Готово к реестру",
        ):
            self.assertIn(label, self.template)
        self.assertIn("invoice-list-quick-filters", self.template)
        self.assertIn("overflow-x: auto", self.css)
        self.assertIn("flex-wrap: nowrap", self.css)

    def test_desktop_keeps_professional_eight_column_table(self):
        header = self.template.split("<thead>", 1)[1].split("</thead>", 1)[0]
        self.assertEqual(header.count("<th>"), 8)
        for label in (
            "Документ",
            "Контрагент",
            "Сумма / остаток",
            "Срок",
            "Статус",
            "Готовность",
            "Ответственный",
            "Действия",
        ):
            self.assertIn(f"<th>{label}</th>", header)
        self.assertIn("invoice-desktop-card-link", self.template)
        desktop_actions = self.template.split(
            '<div class="invoice-desktop-actions">', 1
        )[1].split("</div>", 1)[0]
        self.assertIn("invoice-card-action-icon", desktop_actions)
        self.assertIn(
            '<span class="invoice-desktop-card-label">Открыть</span>',
            desktop_actions,
        )
        self.assertIn(
            'aria-label="Открыть карточку документа {{ invoice.production.title }}"',
            desktop_actions,
        )
        self.assertIn("btn btn-secondary btn-sm invoice-desktop-card-link", desktop_actions)
        self.assertIn(".document-enterprise-table th:last-child", self.css)
        self.assertIn("min-width: 116px", self.css)
        self.assertIn("min-width: 100px", self.css)
        self.assertIn("white-space: nowrap", self.css)
        self.assertIn("overflow-wrap: normal", self.css)
        self.assertIn("word-break: normal", self.css)
        self.assertIn("@media (min-width: 1025px) and (max-width: 1180px)", self.css)
        self.assertIn("min-width: 56px", self.css)
        self.assertIn(".invoice-desktop-card-label", self.css)
        self.assertIn("display: none", self.css)

    def test_tablet_switches_to_two_column_cards(self):
        tablet_css = self.css.split("@media (max-width: 1024px)", 1)[1]
        self.assertIn(
            """.invoice-list-desktop-table {
        display: none;""",
            tablet_css,
        )
        self.assertIn(
            """.invoice-list-mobile-cards {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));""",
            tablet_css,
        )

    def test_mobile_card_has_fixed_business_information_order(self):
        tokens = (
            "invoice-mobile-identity",
            "invoice-mobile-counterparty",
            "invoice-mobile-finance",
            "invoice-mobile-readiness",
            "invoice-mobile-actions",
        )
        positions = [self.template.index(token) for token in tokens]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("invoice-mobile-responsible", self.template)
        self.assertIn("invoice-mobile-card-link", self.template)
        self.assertIn("invoice-card-action-icon", self.template)
        self.assertIn(
            '<span class="invoice-mobile-card-label">Открыть карточку</span>',
            self.template,
        )

    def test_mobile_card_density_removes_redundant_labels(self):
        mobile_block = self.template.split(
            '<div class="invoice-list-mobile-cards"', 1
        )[1]
        self.assertNotIn("<span>Контрагент</span>", mobile_block)
        self.assertIn("gap: 7px", self.css)
        self.assertIn("padding: 11px 12px", self.css)
        self.assertIn("-webkit-line-clamp: 2", self.css)

    def test_mobile_filters_keep_search_and_action_compact(self):
        mobile_css = self.css.split("@media (max-width: 760px)", 1)[1]
        self.assertIn(
            """.invoice-list-primary-filters {
        grid-template-columns: minmax(0, 1fr) auto;""",
            mobile_css,
        )
        self.assertIn(
            """.invoice-list-search-field {
        grid-column: 1 / -1;""",
            mobile_css,
        )
        self.assertIn("min-width: 98px", mobile_css)

    def test_mobile_uses_cards_without_primary_horizontal_scroll(self):
        self.assertIn("@media (max-width: 1024px)", self.css)
        self.assertIn("@media (max-width: 760px)", self.css)
        mobile_css = self.css.split("@media (max-width: 760px)", 1)[1]
        self.assertNotIn(".invoice-list-desktop-table", mobile_css)
        self.assertNotIn("overflow-x: auto", mobile_css)

    def test_mobile_footer_keeps_responsible_and_actions_in_one_row(self):
        tablet_css = self.css.split("@media (max-width: 1024px)", 1)[1]
        self.assertIn(
            """.invoice-mobile-actions {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;""",
            tablet_css,
        )
        self.assertIn("invoice-mobile-responsible", self.template)
        self.assertIn("invoice-mobile-card-link", self.template)

    def test_page_owner_css_has_no_patch_techniques(self):
        self.assertNotIn("!important", self.css)
        self.assertNotIn("nth-child(", self.css)
        self.assertNotIn("rgba(", self.css.lower())
        self.assertNotIn("onclick=", self.template)
        self.assertNotIn("onsubmit=", self.template)
        self.assertNotIn('<details class="enterprise-action-menu">', self.template)
        self.assertNotIn("•••", self.template)
        self.assertNotIn("{% url 'edit_invoice' invoice.id %}", self.template)
        self.assertNotIn("{% url 'invoice_assign_counterparty' invoice.id %}", self.template)
        self.assertNotIn("{% url 'add_to_payment_registry' %}", self.template)
        self.assertEqual(self.template.count(">Карточка</a>"), 0)
        self.assertEqual(
            self.template.count(
                '<span class="invoice-desktop-card-label">Открыть</span>'
            ),
            1,
        )
        self.assertEqual(
            self.template.count(
                '<span class="invoice-mobile-card-label">Открыть карточку</span>'
            ),
            1,
        )


class InvoiceListCompactWorkQueueRenderTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="va3-invoice-list",
            email="va3-invoice-list@example.com",
            password="pass12345",
            is_staff=True,
        )
        self.client.force_login(self.user)
        self.invoice = Invoice.objects.create(
            user=self.user,
            title="VA3.1 responsive density invoice",
            amount=Decimal("125000.00"),
            amount_verified=True,
            status=Invoice.STATUS_APPROVED,
            document_type=Invoice.DOCUMENT_TYPE_INVOICE,
            invoice_number="VA3-1",
            document_date=date(2026, 8, 1),
            planned_payment_date=date(2026, 8, 7),
        )

    def test_render_exposes_compact_filters_and_mobile_representation(self):
        response = self.client.get(reverse("invoice_list"))
        self.assertEqual(response.status_code, 200)
        for token in (
            "Документы к оплате",
            "invoice-card-action-icon",
            "invoice-desktop-card-label",
            "invoice-mobile-card-label",
            "invoice-list-primary-filters",
            "invoice-list-advanced-filters",
            "invoice-list-mobile-cards",
            "invoice-desktop-card-link",
            "invoice-mobile-card-link",
            "invoice-mobile-responsible",
        ):
            self.assertContains(response, token)
