from pathlib import Path
from datetime import datetime

import shutil


def create_database_backup():

    base_dir = Path(__file__).resolve().parent.parent

    db_file = (
        base_dir
        / "db.sqlite3"
    )

    backup_dir = (
        base_dir
        / "backups_db"
    )

    backup_dir.mkdir(
        exist_ok=True
    )

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    backup_file = (
        backup_dir
        / f"db_{timestamp}.sqlite3"
    )

    shutil.copy2(
        db_file,
        backup_file
    )

    return backup_file.name