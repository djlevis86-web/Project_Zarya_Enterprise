import os
import zipfile
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

BACKUP_DIR = os.path.join(
    PROJECT_DIR,
    "backups"
)

os.makedirs(
    BACKUP_DIR,
    exist_ok=True
)

timestamp = datetime.now().strftime(
    "%Y-%m-%d_%H-%M-%S"
)

backup_name = f"Project_Zarya_{timestamp}.zip"

backup_path = os.path.join(
    BACKUP_DIR,
    backup_name
)

EXCLUDE = {
    ".git",
    "venv",
    "__pycache__",
    "node_modules",
    "backups"
}

with zipfile.ZipFile(
    backup_path,
    "w",
    zipfile.ZIP_DEFLATED
) as archive:

    for root, dirs, files in os.walk(PROJECT_DIR):

        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDE
        ]

        for file in files:

            if file.endswith(".pyc"):
                continue

            full_path = os.path.join(
                root,
                file
            )

            rel_path = os.path.relpath(
                full_path,
                PROJECT_DIR
            )

            archive.write(
                full_path,
                rel_path
            )

print()
print("=" * 50)
print("Бэкап создан:")
print(backup_path)
print("=" * 50)
print()