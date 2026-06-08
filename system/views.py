from pathlib import Path

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
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
            x for x in backup_files
            if x.is_file()
        ]

        backup_count = len(
            backup_files
        )

        if backup_files:

            latest_backup = (
                backup_files[0].name
            )

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

    return render(
        request,
        "system/dashboard.html",
        {
            "version": version,
            "backup_count": backup_count,
            "latest_backup": latest_backup,
            "db_size": db_size,
            "changelog_items": changelog_items,
        }
    )


@staff_member_required
def backups_list(request):

    backups_dir = (
        Path(settings.BASE_DIR)
        / "backups"
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