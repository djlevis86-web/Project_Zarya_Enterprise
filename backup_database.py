from pathlib import Path
from datetime import datetime

import shutil


BASE_DIR = Path(__file__).resolve().parent

DB_FILE = BASE_DIR / "db.sqlite3"

BACKUP_DIR = BASE_DIR / "backups_db"

BACKUP_DIR.mkdir(
    exist_ok=True
)

timestamp = datetime.now().strftime(
    "%Y-%m-%d_%H-%M-%S"
)

backup_file = (
    BACKUP_DIR
    / f"db_{timestamp}.sqlite3"
)

shutil.copy2(
    DB_FILE,
    backup_file
)

backups = sorted(
    BACKUP_DIR.glob("*.sqlite3")
)

while len(backups) > 30:

    oldest = backups[0]

    oldest.unlink()

    backups = sorted(
        BACKUP_DIR.glob("*.sqlite3")
    )

print(
    f"Backup created: {backup_file}"
)