import shutil
import subprocess

from django.core.management.base import BaseCommand


OCR_RUNTIME_CHECKS = (
    (
        "pdfinfo",
        "Poppler pdfinfo",
        "Нужен для определения количества страниц PDF.",
    ),
    (
        "pdftoppm",
        "Poppler pdftoppm",
        "Нужен для конвертации страниц PDF в изображения.",
    ),
    (
        "tesseract",
        "Tesseract OCR",
        "Нужен для распознавания текста на изображениях.",
    ),
)


class Command(BaseCommand):
    help = "Check OCR runtime dependencies: Poppler and Tesseract."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fail-on-missing",
            action="store_true",
            help="Return non-zero exit code if any OCR dependency is missing.",
        )

    def handle(self, *args, **options):
        self.stdout.write("OCR runtime diagnostics")
        self.stdout.write("=" * 24)

        missing = []

        for binary_name, title, description in OCR_RUNTIME_CHECKS:
            binary_path = shutil.which(binary_name)

            if binary_path:
                version = self._get_version(binary_name)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"{binary_name}: ok — {binary_path}"
                    )
                )

                if version:
                    self.stdout.write(f"  version: {version}")

            else:
                missing.append(binary_name)

                self.stdout.write(
                    self.style.ERROR(
                        f"{binary_name}: missing — {title}"
                    )
                )
                self.stdout.write(f"  {description}")

        self.stdout.write("")

        if missing:
            self.stdout.write(
                self.style.ERROR(
                    "OCR runtime: unavailable"
                )
            )
            self.stdout.write(
                "Не найдены зависимости: " + ", ".join(missing)
            )
            self.stdout.write(
                "Для OCR PDF нужны Poppler utilities: pdfinfo, pdftoppm."
            )
            self.stdout.write(
                "Для распознавания текста нужен Tesseract OCR с языками rus и eng."
            )

            if options["fail_on_missing"]:
                raise SystemExit(1)

            return

        self.stdout.write(
            self.style.SUCCESS(
                "OCR runtime: available"
            )
        )

    def _get_version(self, binary_name):
        try:
            completed = subprocess.run(
                [binary_name, "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )

        except Exception:
            return ""

        output = (
            completed.stdout
            or completed.stderr
            or ""
        ).strip()

        if not output:
            return ""

        return output.splitlines()[0][:160]
