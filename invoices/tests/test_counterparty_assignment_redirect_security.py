from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from invoices.models import Counterparty, Invoice


class CounterpartyAssignmentRedirectSecurityTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.staff_user = User.objects.create_user(
            username="counterparty-redirect-staff",
            email="counterparty-redirect-staff@example.com",
            password="pass12345",
            is_staff=True,
        )

        self.invoice = Invoice.objects.create(
            user=self.staff_user,
            title="Counterparty redirect security invoice",
            file="invoices/counterparty-redirect-security.pdf",
            amount="1000.00",
            status=Invoice.STATUS_NEW,
        )

        self.counterparty = Counterparty.objects.create(
            name="Counterparty redirect security",
            source=Counterparty.SOURCE_MANUAL,
            is_active=True,
        )

        self.assign_url = reverse(
            "invoice_assign_counterparty",
            kwargs={
                "invoice_id": self.invoice.id,
            },
        )

        self.detail_url = reverse(
            "invoice_detail",
            kwargs={
                "invoice_id": self.invoice.id,
            },
        )

        self.client.force_login(
            self.staff_user
        )

    def post_assignment(self, next_url):
        return self.client.post(
            self.assign_url,
            {
                "counterparty": str(
                    self.counterparty.id
                ),
                "next": next_url,
            },
            HTTP_HOST="testserver",
        )

    def assert_counterparty_assigned(self):
        self.invoice.refresh_from_db()

        self.assertEqual(
            self.invoice.counterparty_id,
            self.counterparty.id,
        )

    def test_local_relative_next_is_allowed(self):
        local_url = reverse(
            "invoice_list"
        )

        response = self.post_assignment(
            local_url
        )

        self.assertRedirects(
            response,
            local_url,
            fetch_redirect_response=False,
        )

        self.assert_counterparty_assigned()

    def test_same_host_absolute_next_is_allowed(self):
        same_host_url = (
            "http://testserver"
            + reverse(
                "invoice_list"
            )
        )

        response = self.post_assignment(
            same_host_url
        )

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertEqual(
            response.headers[
                "Location"
            ],
            same_host_url,
        )

        self.assert_counterparty_assigned()

    def test_external_absolute_next_falls_back_to_invoice_detail(self):
        response = self.post_assignment(
            "https://evil.example/collect"
        )

        self.assertRedirects(
            response,
            self.detail_url,
            fetch_redirect_response=False,
        )

        self.assert_counterparty_assigned()

    def test_protocol_relative_external_next_falls_back_to_invoice_detail(self):
        response = self.post_assignment(
            "//evil.example/collect"
        )

        self.assertRedirects(
            response,
            self.detail_url,
            fetch_redirect_response=False,
        )

        self.assert_counterparty_assigned()

    def test_missing_next_falls_back_to_invoice_detail(self):
        response = self.client.post(
            self.assign_url,
            {
                "counterparty": str(
                    self.counterparty.id
                ),
            },
            HTTP_HOST="testserver",
        )

        self.assertRedirects(
            response,
            self.detail_url,
            fetch_redirect_response=False,
        )

        self.assert_counterparty_assigned()
