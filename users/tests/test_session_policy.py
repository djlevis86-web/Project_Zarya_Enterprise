from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone


class SessionPolicySettingsTests(SimpleTestCase):

    def test_authenticated_session_policy_is_rolling_fourteen_days(self):
        self.assertEqual(
            settings.SESSION_COOKIE_AGE,
            14 * 24 * 60 * 60,
        )
        self.assertIs(
            settings.SESSION_SAVE_EVERY_REQUEST,
            True,
        )
        self.assertIs(
            settings.SESSION_EXPIRE_AT_BROWSER_CLOSE,
            False,
        )


class RollingSessionIntegrationTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="rolling-session-user",
            email="rolling-session-user@example.com",
            password="pass12345",
            is_staff=True,
        )

    def test_authenticated_request_refreshes_cookie_lifetime(self):
        self.client.force_login(
            self.user
        )

        session_key = self.client.session.session_key

        response = self.client.get(
            reverse("dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            self.client.session.session_key,
            session_key,
        )
        self.assertIn(
            settings.SESSION_COOKIE_NAME,
            response.cookies,
        )

        session_cookie = response.cookies[
            settings.SESSION_COOKIE_NAME
        ]

        self.assertEqual(
            int(session_cookie["max-age"]),
            settings.SESSION_COOKIE_AGE,
        )
        self.assertFalse(
            self.client.session.get_expire_at_browser_close()
        )

    def test_active_request_extends_database_expiry(self):
        self.client.force_login(
            self.user
        )

        session_key = self.client.session.session_key
        session = Session.objects.get(
            session_key=session_key
        )
        session.expire_date = (
            timezone.now()
            + timedelta(minutes=5)
        )
        session.save(
            update_fields=["expire_date"]
        )

        request_started_at = timezone.now()

        response = self.client.get(
            reverse("dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        session.refresh_from_db()

        self.assertGreater(
            session.expire_date,
            request_started_at + timedelta(days=13),
        )

    def test_logout_invalidates_session(self):
        self.client.force_login(
            self.user
        )

        session_key = self.client.session.session_key

        response = self.client.get(
            reverse("logout")
        )

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertFalse(
            Session.objects.filter(
                session_key=session_key
            ).exists()
        )
        self.assertIn(
            settings.SESSION_COOKIE_NAME,
            response.cookies,
        )
        self.assertEqual(
            int(
                response.cookies[
                    settings.SESSION_COOKIE_NAME
                ]["max-age"]
            ),
            0,
        )
