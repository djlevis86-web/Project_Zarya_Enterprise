import requests


def get_github_version(repo_name):

    try:

        url = (
            f"https://api.github.com/repos/"
            f"{repo_name}/tags"
        )

        response = requests.get(
            url,
            timeout=10
        )

        if response.status_code == 200:

            tags = response.json()

            if tags:

                return tags[0]["name"]

    except Exception as e:

        print(
            "GitHub version error:",
            e
        )

    return None