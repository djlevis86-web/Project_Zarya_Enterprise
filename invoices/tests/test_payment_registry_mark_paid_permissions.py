from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from invoices.models import PaymentRegistry


class PaymentRegistryMarkPaidPermissionTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="registry-paid-owner",
            email="registry-paid-owner@example.com",
            password="pass12345",
            is_staff=False,
            is_superuser=False,
        )

        self.actor = User.objects.create_user(
            username="registry-paid-actor",
            email="registry-paid-actor@example.com",
            password="pass12345",
            is_staff=False,
            is_superuser=False,
        )

        permission = Permission.objects.get(
            content_type__app_label="invoices",
            codename="can_mark_payment_registry_paid",
        )

        self.owner.user_permissions.add(
            permission
        )
        self.actor.user_permissions.add(
            permission
        )

        self.registry = PaymentRegistry.objects.create(
            title="Permission test registry",
            status=PaymentRegistry.STATUS_DRAFT,
            created_by=self.owner,
        )

        self.url = reverse(
            "mark_payment_registry_paid",
            kwargs={
                "registry_id": self.registry.id,
            },
        )

    @patch(
        "invoices.view_modules.payment_registry_action_views."
        "mark_payment_registry_as_paid"
    )
    def test_non_owner_with_permission_receives_403(
        self,
        mark_paid_mock,
    ):
        self.client.force_login(
            self.actor
        )

        response = self.client.post(
            self.url
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        mark_paid_mock.assert_not_called()

        self.registry.refresh_from_db()

        self.assertEqual(
            self.registry.status,
            PaymentRegistry.STATUS_DRAFT,
        )

    @patch(
        "invoices.view_modules.payment_registry_action_views."
        "mark_payment_registry_as_paid"
    )
    def test_owner_with_permission_reaches_payment_service(
        self,
        mark_paid_mock,
    ):
        mark_paid_mock.return_value = {
            "paid_count": 0,
            "skipped_count": 0,
        }

        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            self.url
        )

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertEqual(
            response.url,
            reverse(
                "payment_registry_detail",
                kwargs={
                    "registry_id": self.registry.id,
                },
            ),
        )

        mark_paid_mock.assert_called_once()

        called_registry = mark_paid_mock.call_args.args[
            0
        ]
        called_user = mark_paid_mock.call_args.kwargs[
            "user"
        ]

        self.assertEqual(
            called_registry.id,
            self.registry.id,
        )
        self.assertEqual(
            called_user.id,
            self.owner.id,
        )
