from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def project_version(request):

    version_file = BASE_DIR / 'VERSION'

    try:

        version = version_file.read_text(
            encoding='utf-8'
        ).strip()

    except Exception:

        version = 'unknown'

    return {
        'PROJECT_VERSION': version
    }