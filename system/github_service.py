import requests


def get_github_version(repo_name):

    try:

        url = (
            f"https://raw.githubusercontent.com/"
            f"{repo_name}/main/VERSION"
        )

        response = requests.get(
            url,
            timeout=10
        )

        if response.status_code == 200:

            return (
                response.text
                .strip()
            )

    except Exception:
        pass

    return None