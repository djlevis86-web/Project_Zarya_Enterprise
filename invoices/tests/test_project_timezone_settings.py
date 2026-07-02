from django.conf import settings
from django.test import SimpleTestCase


class ProjectTimezoneSettingsTests(SimpleTestCase):

    def test_project_uses_moscow_timezone(self):
        self.assertEqual(
            settings.TIME_ZONE,
            "Europe/Moscow",
        )

    def test_project_keeps_timezone_aware_datetimes_enabled(self):
        self.assertTrue(
            settings.USE_TZ,
        )
