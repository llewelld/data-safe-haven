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

# Mirror server configuration

MIRROR_SERVER_TOKEN_NAME: str = "mirror_api_token"  # noqa: S105
MIRROR_SERVER_URL: str = os.environ["MIRROR_SERVER_URL"]
MIRROR_SERVER_USERNAME: str = os.environ["MIRROR_SERVER_USERNAME"]
MIRROR_SERVER_PASSWORD: str = os.environ["MIRROR_SERVER_PASSWORD"]

# Workspace server configuration
WORKSPACE_SERVER_TOKEN_NAME: str = "push_mirror_api_token"  # noqa: S105
WORKSPACE_SERVER_URL: str = os.environ["WORKSPACE_SERVER_URL"]
WORKSPACE_SERVER_USERNAME: str = os.environ["WORKSPACE_SERVER_USERNAME"]
WORKSPACE_SERVER_PASSWORD: str = os.environ["WORKSPACE_SERVER_PASSWORD"]

REPOSITORY_DATA: dict[str, list[dict[str, str]]] = json.loads(
    os.environ["REPOSITORY_DATA"]
)


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
    repostiory_url: str,
    repository_name: str,
    repository_auth_token: str,
    gitea_url: str,
    token: str,
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
        f"{gitea_url}/api/v1/repos/migrate",
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
    gitea_url: str,
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
        f"{gitea_url}/api/v1/repos/{owner}/{repository}/push_mirrors",
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


def synchronise_push_mirrors(
    owner: str, repository: str, gitea_url: str, token: str
) -> None:
    logger.info(f"Synchronising all push mirrors for {owner}/{repository}")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    params: dict[str, str] = {"access_token": token}

    response: Response = requests.post(
        f"{gitea_url}/api/v1/repos/{owner}/{repository}/push_mirrors-sync",
        params=params,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )

    if not response.status_code == requests.codes.ok:
        error_message: str = (
            f"Cannot synchronise push mirrors for repository {repository}. Status code: {response.status_code}. Response {response.json()}"
        )

        raise Exception(error_message)

    logger.info(f"Push mirrors synchronised for {owner}/{repository}")


def main() -> None:
    migration_token = obtain_api_token(
        token_name=MIRROR_SERVER_TOKEN_NAME,
        username=MIRROR_SERVER_USERNAME,
        password=MIRROR_SERVER_PASSWORD,
        scopes=["write:repository"],
        gitea_url=MIRROR_SERVER_URL,
    )

    push_mirror_token = obtain_api_token(
        token_name=WORKSPACE_SERVER_TOKEN_NAME,
        username=WORKSPACE_SERVER_USERNAME,
        password=WORKSPACE_SERVER_PASSWORD,
        gitea_url=WORKSPACE_SERVER_URL,
        scopes=["write:repository", "write:user"],
    )

    for repository in REPOSITORY_DATA["repositories"]:
        delete_repository(
            username=MIRROR_SERVER_USERNAME,
            gitea_url=MIRROR_SERVER_URL,
            repository_name=repository["repository_name"],
            token=migration_token,
        )

        create_migration(
            repository_name=repository["repository_name"],
            repostiory_url=repository["repository_url"],
            repository_auth_token=repository["repository_auth_token"],
            gitea_url=MIRROR_SERVER_URL,
            token=migration_token,
        )

        delete_repository(
            username=WORKSPACE_SERVER_USERNAME,
            gitea_url=WORKSPACE_SERVER_URL,
            repository_name=f"{repository['repository_name']}-mirror",
            token=push_mirror_token,
        )

        remote_address: str = create_repository(
            user_name=WORKSPACE_SERVER_USERNAME,
            repository_name=f"{repository['repository_name']}-mirror",
            gitea_url=WORKSPACE_SERVER_URL,
            token=push_mirror_token,
        )

        create_push_mirror(
            owner=MIRROR_SERVER_USERNAME,
            repository=repository["repository_name"],
            remote_address=remote_address,
            remote_username=WORKSPACE_SERVER_USERNAME,
            remote_password=WORKSPACE_SERVER_PASSWORD,
            gitea_url=MIRROR_SERVER_URL,
            token=migration_token,
        )

        synchronise_push_mirrors(
            owner=MIRROR_SERVER_USERNAME,
            repository=repository["repository_name"],
            gitea_url=MIRROR_SERVER_URL,
            token=migration_token,
        )


if __name__ == "__main__":
    main()
