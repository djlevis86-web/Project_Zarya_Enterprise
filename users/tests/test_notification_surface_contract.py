from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class NotificationSurfaceContractTests(SimpleTestCase):
    def setUp(self):
        self.base = Path(settings.BASE_DIR)
        self.template = (self.base / "templates/base.html").read_text(
            encoding="utf-8-sig"
        )
        self.css = (
            self.base / "static/css/components/modals.css"
        ).read_text(encoding="utf-8-sig")

    def test_messages_use_semantic_svg_notification_markup(self):
        expected = (
            "class="
            + chr(34)
            + "z-toast tone-{{ message.tags|default:'info' }}"
            + chr(34)
        )
        self.assertIn(expected, self.template)
        self.assertNotIn('class="alert alert-{{ message.tags', self.template)
        self.assertIn('class="z-toast-icon"', self.template)
        self.assertIn('viewBox="0 0 24 24"', self.template)
        self.assertIn("data-toast-region", self.template)
        self.assertIn("data-toast-close", self.template)
        self.assertIn('title="Закрыть"', self.template)

    def test_notification_region_is_fixed_top_right_overlay(self):
        block = self.css.split(".z-toast-region {", 1)[1].split("}", 1)[0]
        self.assertIn("position: fixed", block)
        self.assertIn("top: calc(var(--zds-topbar-height) + 16px)", block)
        self.assertIn("right: 20px", block)
        self.assertIn("z-index: 900", block)
        self.assertIn("width: min(480px, calc(100vw - 40px))", block)
        self.assertIn("max-height: calc(100vh - var(--zds-topbar-height) - 32px)", block)
        self.assertIn("margin: 0", block)
        self.assertIn("overflow-y: auto", block)
        self.assertIn("pointer-events: none", block)
        self.assertNotIn("position: relative", block)
        self.assertNotIn("margin: 0 0 10px", block)

        toast = self.css.split(".z-toast {", 1)[1].split("}", 1)[0]
        self.assertIn("width: 100%", toast)
        self.assertIn("min-height: 44px", toast)
        self.assertIn("grid-template-columns: 20px minmax(0, 1fr) 28px", toast)
        self.assertIn("pointer-events: auto", toast)

    def test_overlay_layering_controls_and_mobile_fallback_are_safe(self):
        drawer = self.css.split(".z-drawer {", 1)[1].split("}", 1)[0]
        self.assertIn("z-index: 1200", drawer)
        self.assertIn("z-index: 900", self.css)

        close = self.css.split(".z-toast-close {", 1)[1].split("}", 1)[0]
        self.assertIn("width: 28px", close)
        self.assertIn("border: 0", close)
        self.assertIn("background: transparent", close)

        for token in (
            "top: 80px",
            "right: 12px",
            "left: 12px",
            "width: auto",
            "max-height: calc(100dvh - 92px)",
            "grid-template-columns: 18px minmax(0, 1fr) 28px",
            ".z-toast.tone-success",
            ".z-toast.tone-warning",
            ".z-toast.tone-error",
            "var(--zds-color-success)",
            "var(--zds-color-warning)",
            "var(--zds-color-danger)",
        ):
            self.assertIn(token, self.css)
