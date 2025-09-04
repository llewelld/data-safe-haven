import json
import logging
import os
from typing import Any

import requests
from requests import Response
from requests.auth import HTTPBasicAuth

logger = logging.getLogger("mirror_manager")
logging.basicConfig(level=logging.INFO)

DEFAULT_TIMEOUT: int = 5 * 60

# Migration configuration

TOKEN_NAME: str = "mirror_api_token"  # noqa: S105
GITEA_URL: str = os.environ["GITEA_URL"]
MIRROR_USERNAME: str = os.environ["MIRROR_USERNAME"]
MIRROR_PASSWORD: str = os.environ["MIRROR_PASSWORD"]

# Push mirror configuration
PUSH_MIRROR_TOKEN_NAME: str = "push_mirror_api_token"  # noqa: S105
PUSH_MIRROR_GITEA_URL: str = os.environ["PUSH_MIRROR_GITEA_URL"]
PUSH_MIRROR_USERNAME: str = os.environ["PUSH_MIRROR_USERNAME"]
PUSH_MIRROR_PASSWORD: str = os.environ["PUSH_MIRROR_PASSWORD"]

# TODO(cgavidia): Testing workarounds
REPOSITORY_AUTH_TOKEN: str = os.environ["REPOSITORY_AUTH_TOKEN"]


def load_repository_data() -> list[dict[str, str]]:
    # TODO(cgavidia) : Load from config. Or environment variables.
    return [
        {
            "repository_name": "data-safe-haven",
            "repository_url": "https://github.com/cptanalatriste/data-safe-haven",
            "repository_auth_token": REPOSITORY_AUTH_TOKEN,
        }
    ]


def delete_token(username: str, password: str, token_name: str, gitea_url: str) -> None:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    basic_auth = HTTPBasicAuth(username, password)

    response: Response = requests.delete(
        f"{gitea_url}/api/v1/users/{username}/tokens/{token_name}",
        auth=basic_auth,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )

    if not response.status_code == requests.codes.no_content:
        logging.info(
            f"Cannot delete token {token_name} for user {username}. Status code: {response.status_code}"
        )
    else:
        logging.info(
            f"Token {token_name} for user {username} deleted. Status code: {response.status_code}"
        )


def create_token(
    username: str, password: str, token_name: str, gitea_url: str, scopes: list[str]
) -> Any:
    logger.info(f"Creating API token {token_name} for user {username}")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    basic_auth = HTTPBasicAuth(username, password)
    data: dict[str, str | list[str]] = {
        "name": token_name,
        "scopes": scopes,
    }

    response: Response = requests.post(
        f"{gitea_url}/api/v1/users/{username}/tokens",
        auth=basic_auth,
        headers=headers,
        data=json.dumps(data),
        timeout=DEFAULT_TIMEOUT,
    )

    if not response.status_code == requests.codes.created:
        error_message: str = (
            f"Cannot create tokens for user {username}. Status code: {response.status_code}. Response {response.json()}"
        )

        raise Exception(error_message)

    return response.json()["sha1"]


def create_migration(
    repostiory_url: str, repository_name: str, repository_auth_token: str, token: str
) -> None:
    logger.info(f"Creating a migration for repository {repostiory_url}")

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
            f"Cannot create migration for repository {repostiory_url}. Status code: {response.status_code}. Response {response.json()}"
        )

        raise Exception(error_message)
    else:
        logger.info(f"Migration created at {response.json()['html_url']}")


def delete_repository(
    username: str, gitea_url: str, repository_name: str, token: str
) -> None:
    logger.info(
        f"Attempting to delete repository {repository_name} for user {username}"
    )

    headers: dict[str, str] = {"Content-Type": "application/json"}
    params: dict[str, str] = {"access_token": token}

    response: Response = requests.delete(
        f"{gitea_url}/api/v1/repos/{username}/{repository_name}",
        params=params,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )

    if response.status_code == requests.codes.no_content:
        logging.info("Repository successfully deleted.")
    else:
        logging.info("Cannot delete repository.")


def obtain_api_token(
    token_name: str, username: str, password: str, scopes: list[str], gitea_url: str
) -> Any:
    delete_token(
        username=username, password=password, token_name=token_name, gitea_url=gitea_url
    )

    token_value = create_token(
        username=username,
        password=password,
        token_name=token_name,
        scopes=scopes,
        gitea_url=gitea_url,
    )

    return token_value


def create_push_mirror(
    owner: str,
    repository: str,
    remote_address: str,
    remote_password: str,
    remote_username: str,
    token: str,
) -> None:
    logger.info(f"Creating a push mirror  for {repository} to {remote_address}")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    params: dict[str, str] = {"access_token": token}

    data: dict[str, str | bool] = {
        "interval": "0h10m0s",
        "remote_address": remote_address,
        "remote_password": remote_password,
        "remote_username": remote_username,
        "sync_on_commit": True,
    }

    response: Response = requests.post(
        f"{GITEA_URL}/api/v1/repos/{owner}/{repository}/push_mirrors",
        params=params,
        headers=headers,
        data=json.dumps(data),
        timeout=DEFAULT_TIMEOUT,
    )

    if not response.status_code == requests.codes.ok:
        error_message: str = (
            f"Cannot create push mirror for repository {repository}. Status code: {response.status_code}. Response {response.json()}"
        )

        raise Exception(error_message)

    logger.info(f"Push mirror created to {remote_address}")


def create_repository(
    user_name: str, repository_name: str, gitea_url: str, token: str
) -> Any:
    logger.info(f"Creating repository {repository_name} for user {user_name}")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    params: dict[str, str] = {"access_token": token}

    data: dict[str, str | bool] = {
        "name": repository_name,
        "private": False,
    }

    response: Response = requests.post(
        f"{gitea_url}/api/v1/user/repos",
        params=params,
        headers=headers,
        data=json.dumps(data),
        timeout=DEFAULT_TIMEOUT,
    )

    if not response.status_code == requests.codes.created:
        error_message: str = (
            f"Cannot create repository {repository_name} for user {user_name}. Status code: {response.status_code}. Response {response.json()}"
        )

        raise Exception(error_message)

    logger.info(f"Repository created at {response.json()['html_url']}")
    return response.json()["clone_url"]


def main() -> None:
    migration_token = obtain_api_token(
        token_name=TOKEN_NAME,
        username=MIRROR_USERNAME,
        password=MIRROR_PASSWORD,
        scopes=["write:repository"],
        gitea_url=GITEA_URL,
    )

    push_mirror_token = obtain_api_token(
        token_name=PUSH_MIRROR_TOKEN_NAME,
        username=PUSH_MIRROR_USERNAME,
        password=PUSH_MIRROR_PASSWORD,
        gitea_url=PUSH_MIRROR_GITEA_URL,
        scopes=["write:repository", "write:user"],
    )

    repository_data: list[dict[str, str]] = load_repository_data()

    for repository in repository_data:
        delete_repository(
            username=MIRROR_USERNAME,
            gitea_url=GITEA_URL,
            repository_name=repository["repository_name"],
            token=migration_token,
        )

        create_migration(
            repository_name=repository["repository_name"],
            repostiory_url=repository["repository_url"],
            repository_auth_token=repository["repository_auth_token"],
            token=migration_token,
        )

        delete_repository(
            username=PUSH_MIRROR_USERNAME,
            gitea_url=PUSH_MIRROR_GITEA_URL,
            repository_name=f"{repository['repository_name']}-mirror",
            token=push_mirror_token,
        )

        remote_address: str = create_repository(
            user_name=PUSH_MIRROR_USERNAME,
            repository_name=f"{repository['repository_name']}-mirror",
            gitea_url=PUSH_MIRROR_GITEA_URL,
            token=push_mirror_token,
        )

        create_push_mirror(
            owner=MIRROR_USERNAME,
            repository=repository["repository_name"],
            remote_address=remote_address,
            remote_username=PUSH_MIRROR_USERNAME,
            remote_password=PUSH_MIRROR_PASSWORD,
            token=migration_token,
        )


if __name__ == "__main__":
    main()
