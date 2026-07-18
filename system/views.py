import os
import platform
import subprocess
from pathlib import Path

import django

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from users.permissions import system_admin_required
from django.http import (
    FileResponse,
    Http404,
)
from django.shortcuts import (
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from invoices.models import Invoice
from users.models import User

from audit.models import AuditLog
from audit.services import log_action

from .github_service import get_github_version
from .services import create_database_backup


def get_ocr_job_model():

    for app_label in (
        'invoices',
        'ocr',
    ):

        try:

            return apps.get_model(
                app_label,
                'OCRJob'
            )

        except LookupError:

            continue

    return None


def get_ocr_stats():

    OCRJob = get_ocr_job_model()

    if OCRJob is None:

        return {
            'ocr_total': 0,
            'ocr_pending': 0,
            'ocr_processing': 0,
            'ocr_done': 0,
            'ocr_error': 0,
        }

    return {
        'ocr_total': OCRJob.objects.count(),
        'ocr_pending': OCRJob.objects.filter(
            status=getattr(
                OCRJob,
                'STATUS_PENDING',
                'pending'
            )
        ).count(),
        'ocr_processing': OCRJob.objects.filter(
            status=getattr(
                OCRJob,
                'STATUS_PROCESSING',
                'processing'
            )
        ).count(),
        'ocr_done': OCRJob.objects.filter(
            status=getattr(
                OCRJob,
                'STATUS_DONE',
                'done'
            )
        ).count(),
        'ocr_error': OCRJob.objects.filter(
            status=getattr(
                OCRJob,
                'STATUS_ERROR',
                'error'
            )
        ).count(),
    }


@system_admin_required
def system_dashboard(request):

    version = "unknown"

    try:

        version = (
            Path(settings.BASE_DIR)
            / "VERSION"
        ).read_text(
            encoding="utf-8"
        ).strip()

    except Exception:

        pass

    backups_dir = (
        Path(settings.BASE_DIR)
        / "backups"
    )

    backup_count = 0

    latest_backup = "-"

    if backups_dir.exists():

        backup_files = sorted(
            backups_dir.glob("*"),
            reverse=True
        )

        backup_files = [
            backup_file
            for backup_file in backup_files
            if backup_file.is_file()
        ]

        backup_count = len(
            backup_files
        )

        if backup_files:

            latest_backup = backup_files[0].name

    db_backups_dir = (
        Path(settings.BASE_DIR)
        / "backups_db"
    )

    db_backup_count = 0

    latest_db_backup = "-"

    if db_backups_dir.exists():

        db_backup_files = sorted(
            db_backups_dir.glob("*.sqlite3"),
            reverse=True
        )

        db_backup_count = len(
            db_backup_files
        )

        if db_backup_files:

            latest_db_backup = db_backup_files[0].name

    db_size = 0

    try:

        db_file = (
            Path(settings.BASE_DIR)
            / "db.sqlite3"
        )

        db_size = round(
            db_file.stat().st_size
            / 1024
            / 1024,
            2
        )

    except Exception:

        pass

    python_version = platform.python_version()

    django_version = django.get_version()

    git_branch = "-"

    try:

        git_branch = (
            subprocess.check_output(
                [
                    "git",
                    "branch",
                    "--show-current",
                ],
                cwd=settings.BASE_DIR
            )
            .decode()
            .strip()
        )

    except Exception:

        pass

    last_commit = "-"

    try:

        last_commit = (
            subprocess.check_output(
                [
                    "git",
                    "log",
                    "-1",
                    "--pretty=%h %s",
                ],
                cwd=settings.BASE_DIR
            )
            .decode()
            .strip()
        )

    except Exception:

        pass

    try:

        invoice_count = Invoice.objects.count()

    except Exception:

        invoice_count = 0

    try:

        user_count = User.objects.count()

    except Exception:

        user_count = 0

    changelog_items = []

    try:

        changelog_file = (
            Path(settings.BASE_DIR)
            / "CHANGELOG.md"
        )

        lines = changelog_file.read_text(
            encoding="utf-8"
        ).splitlines()

        collect = False

        for line in lines:

            line = line.strip()

            if line.startswith("###"):

                collect = True
                continue

            if collect:

                if line.startswith("---"):

                    break

                if line.startswith("- "):

                    changelog_items.append(
                        line[2:]
                    )

    except Exception:

        pass

    ocr_stats = get_ocr_stats()

    context = {
        "version": version,
        "backup_count": backup_count,
        "latest_backup": latest_backup,
        "db_backup_count": db_backup_count,
        "latest_db_backup": latest_db_backup,
        "db_size": db_size,
        "changelog_items": changelog_items,
        "python_version": python_version,
        "django_version": django_version,
        "invoice_count": invoice_count,
        "user_count": user_count,
        "git_branch": git_branch,
        "last_commit": last_commit,
    }

    context.update(
        ocr_stats
    )

    return render(
        request,
        "system/dashboard.html",
        context
    )


@system_admin_required
def backups_list(request):

    backups_dir = (
        Path(settings.BASE_DIR)
        / "backups_db"
    )

    backups = []

    if backups_dir.exists():

        for backup_file in sorted(
            backups_dir.glob("*"),
            reverse=True
        ):

            if backup_file.is_file():

                backups.append(
                    {
                        "name": backup_file.name,
                        "size": round(
                            backup_file.stat().st_size
                            / 1024
                            / 1024,
                            2
                        ),
                        "created": backup_file.stat().st_mtime,
                    }
                )

    return render(
        request,
        "system/backups.html",
        {
            "backups": backups,
        }
    )


@system_admin_required
@require_POST
def create_backup(request):

    try:

        filename = create_database_backup()

        messages.success(
            request,
            f"Создана резервная копия: {filename}"
        )

        log_action(
            request=request,
            action=AuditLog.ACTION_BACKUP,
            object_type="Backup",
            object_id=filename,
            object_repr=filename,
            message="Создана резервная копия базы данных.",
            metadata={
                "event": "backup_created",
                "filename": filename,
            },
        )

    except Exception as error:

        messages.error(
            request,
            f"Ошибка создания резервной копии: {error}"
        )

        log_action(
            request=request,
            action=AuditLog.ACTION_BACKUP,
            object_type="Backup",
            object_repr="Создание бэкапа",
            message=f"Ошибка создания резервной копии: {error}",
            metadata={
                "event": "backup_create_failed",
                "error": str(error),
            },
        )

    return redirect(
        "system_dashboard"
    )


@system_admin_required
def download_backup(request, filename):

    backup_file = (
        Path(settings.BASE_DIR)
        / "backups_db"
        / filename
    )

    if not backup_file.exists():

        raise Http404(
            "Файл не найден"
        )

    log_action(
        request=request,
        action=AuditLog.ACTION_BACKUP,
        object_type="Backup",
        object_id=filename,
        object_repr=filename,
        message="Скачана резервная копия базы данных.",
        metadata={
            "event": "backup_downloaded",
            "filename": filename,
            "size_bytes": backup_file.stat().st_size,
        },
    )

    return FileResponse(
        open(
            backup_file,
            "rb"
        ),
        as_attachment=True,
        filename=filename
    )


@system_admin_required
@require_POST
def delete_backup(request, filename):

    backup_file = (
        Path(settings.BASE_DIR)
        / "backups_db"
        / filename
    )

    try:

        if backup_file.exists():

            size_bytes = backup_file.stat().st_size

            backup_file.unlink()

            messages.success(
                request,
                f"Удалён бэкап: {filename}"
            )

            log_action(
                request=request,
                action=AuditLog.ACTION_BACKUP,
                object_type="Backup",
                object_id=filename,
                object_repr=filename,
                message="Удалена резервная копия базы данных.",
                metadata={
                    "event": "backup_deleted",
                    "filename": filename,
                    "size_bytes": size_bytes,
                },
            )

    except Exception as error:

        messages.error(
            request,
            f"Ошибка удаления: {error}"
        )

        log_action(
            request=request,
            action=AuditLog.ACTION_BACKUP,
            object_type="Backup",
            object_id=filename,
            object_repr=filename,
            message=f"Ошибка удаления резервной копии: {error}",
            metadata={
                "event": "backup_delete_failed",
                "filename": filename,
                "error": str(error),
            },
        )

    return redirect(
        "backups_list"
    )


@system_admin_required
def versions_page(request):

    version = "-"

    try:

        version = (
            Path(settings.BASE_DIR)
            / "VERSION"
        ).read_text(
            encoding="utf-8"
        ).strip()

    except Exception:

        pass

    git_branch = "-"

    try:

        git_branch = (
            subprocess.check_output(
                [
                    "git",
                    "branch",
                    "--show-current",
                ],
                cwd=settings.BASE_DIR
            )
            .decode()
            .strip()
        )

    except Exception:

        pass

    commits = []

    try:

        output = (
            subprocess.check_output(
                [
                    "git",
                    "log",
                    "-10",
                    "--pretty=format:%h|%ad|%s",
                    "--date=short",
                ],
                cwd=settings.BASE_DIR
            )
            .decode()
            .splitlines()
        )

        for row in output:

            parts = row.split("|")

            if len(parts) >= 3:

                commits.append(
                    {
                        "hash": parts[0],
                        "date": parts[1],
                        "message": parts[2],
                    }
                )

    except Exception:

        pass

    return render(
        request,
        "system/versions.html",
        {
            "version": version,
            "git_branch": git_branch,
            "commits": commits,
        }
    )


@system_admin_required
def updates_page(request):

    local_version = "-"

    try:

        local_version = (
            Path(settings.BASE_DIR)
            / "VERSION"
        ).read_text(
            encoding="utf-8"
        ).strip()

    except Exception:

        pass

    github_repo = os.getenv(
        "GITHUB_REPO"
    )

    github_version = (
        get_github_version(
            github_repo
        )
        if github_repo
        else None
    )

    update_available = False

    if github_version:

        update_available = (
            github_version
            != local_version
        )

    return render(
        request,
        "system/updates.html",
        {
            "local_version": local_version,
            "github_version": (
                github_version
                or "не удалось получить"
            ),
            "update_available": update_available,
        }
    )


@system_admin_required
def maintenance_page(request):

    return render(
        request,
        "system/maintenance.html"
    )
