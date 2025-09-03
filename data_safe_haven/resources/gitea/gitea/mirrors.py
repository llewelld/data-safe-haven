import json
import logging
import os

import requests
from requests import Response
from requests.auth import HTTPBasicAuth

logger = logging.getLogger("mirror_manager")
logging.basicConfig(level=logging.INFO)

DEFAULT_TIMEOUT: int = 5 * 60

TOKEN_NAME: str = "mirror_api_token"  # noqa: S105
GITEA_URL: str = os.environ["GITEA_URL"]
MIRROR_USERNAME: str = os.environ["MIRROR_USERNAME"]
MIRROR_PASSWORD: str = os.environ["MIRROR_PASSWORD"]

# TODO(cgavidia): Testing workarounds
MIRROR_USER_TOKEN: str = os.environ["MIRROR_USER_TOKEN"]
REPOSITORY_AUTH_TOKEN: str = os.environ["REPOSITORY_AUTH_TOKEN"]


def store_token(token: str) -> None:
    # TODO(cgavidia): Store this value in secrets.
    pass


def load_repository_data() -> list[dict[str, str]]:
    # TODO(cgavidia) : Load from config. Or environment variables.
    return [
        {
            "repository_name": "data-safe-haven-mirror",
            "repository_url": "https://github.com/cptanalatriste/data-safe-haven",
            "repository_auth_token": REPOSITORY_AUTH_TOKEN,
        }
    ]


def retrieve_token() -> str:
    # TODO(cgavidia): Get this value from secrets
    return MIRROR_USER_TOKEN


def get_tokens_by_name() -> list[dict]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    basic_auth = HTTPBasicAuth(MIRROR_USERNAME, MIRROR_PASSWORD)

    response: Response = requests.get(
        f"{GITEA_URL}/api/v1/users/{MIRROR_USERNAME}/tokens",
        auth=basic_auth,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )

    if not response.status_code == requests.codes.ok:
        error_message: str = (
            f"Cannot retrieve tokens for user {MIRROR_USERNAME}. Status code: {response.status_code}"
        )
        raise Exception(error_message)

    return [token for token in response.json() if token["name"] == TOKEN_NAME]


def create_token() -> str:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    basic_auth = HTTPBasicAuth(MIRROR_USERNAME, MIRROR_PASSWORD)
    data: dict[str, str | list[str]] = {
        "name": TOKEN_NAME,
        "scopes": ["write:repository"],
    }

    response: Response = requests.post(
        f"{GITEA_URL}/api/v1/users/{MIRROR_USERNAME}/tokens",
        auth=basic_auth,
        headers=headers,
        data=json.dumps(data),
        timeout=DEFAULT_TIMEOUT,
    )

    if not response.status_code == requests.codes.created:
        error_message: str = (
            f"Cannot create tokens for user {MIRROR_USERNAME}. Status code: {response.status_code}. Response {response.json()}"
        )

        raise Exception(error_message)

    return response.json()["sha1"]


def create_migration(
    repostiory_url: str, repository_name: str, repository_auth_token: str, token: str
) -> None:
    logger.info(f"Creating a mirror for repository {repostiory_url}")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    params: dict[str, str] = {"access_token": token}

    data: dict[str, str | bool] = {
        "clone_addr": repostiory_url,
        "auth_token": repository_auth_token,
        "mirror": True,
        "mirror_interval": "0h10m0s",
        "private": False,
        "repo_name": repository_name,
        "service": "github",
    }

    response: Response = requests.post(
        f"{GITEA_URL}/api/v1/repos/migrate",
        params=params,
        headers=headers,
        data=json.dumps(data),
        timeout=DEFAULT_TIMEOUT,
    )

    if not response.status_code == requests.codes.created:
        error_message: str = (
            f"Cannot create mirror for repositor {repostiory_url}. Status code: {response.status_code}. Response {response.json()}"
        )

        raise Exception(error_message)
    else:
        logger.info(f"Mirror created at {response.json()['html_url']}")


def delete_repository(repository_name: str, token: str) -> None:
    logger.info(
        f"Attempting to delete repository {repository_name} for user {MIRROR_USERNAME}"
    )

    headers: dict[str, str] = {"Content-Type": "application/json"}
    params: dict[str, str] = {"access_token": token}

    requests.delete(
        f"{GITEA_URL}/api/v1/repos/{MIRROR_USERNAME}/{repository_name}",
        params=params,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )


def main() -> None:
    tokens: list[dict[str, str]] = get_tokens_by_name()

    token: str | None = None
    if not tokens:
        token = create_token()
        store_token(token)

    token = retrieve_token()
    repository_data: list[dict[str, str]] = load_repository_data()

    for repository in repository_data:
        delete_repository(repository["repository_name"], token=token)

        create_migration(
            repository_name=repository["repository_name"],
            repostiory_url=repository["repository_url"],
            repository_auth_token=repository["repository_auth_token"],
            token=token,
        )


if __name__ == "__main__":
    main()
