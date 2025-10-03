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
    service: str,
) -> tuple[Any, Any]:
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
        "service": service,
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

    logger.info(
        f"Migration created for user {response.json()['owner']['username']} at repository {response.json()['name']}"
    )
    return response.json()["owner"]["username"], response.json()["name"]


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
        logging.info(f"Cannot delete repository. Response {response.json()}")


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


def get_repositories(owner: str, gitea_url: str, token: str) -> list[str]:
    logger.info(f"Searching for repositories of {owner} at {gitea_url}")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    params: dict[str, str] = {"access_token": token}

    response: Response = requests.get(
        f"{gitea_url}/api/v1/repos/search",
        params=params,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )

    if not response.status_code == requests.codes.ok:
        error_message: str = (
            f"Could not list repositories for user {owner}. Status code: {response.status_code}. Response {response.json()}"
        )

        raise Exception(error_message)

    return [
        repository["name"]
        for repository in response.json()["data"]
        if repository["owner"]["username"] == owner
    ]


def main() -> None:
    gitea_mirror_token = obtain_api_token(
        token_name=MIRROR_SERVER_TOKEN_NAME,
        username=MIRROR_SERVER_USERNAME,
        password=MIRROR_SERVER_PASSWORD,
        scopes=["write:repository"],
        gitea_url=MIRROR_SERVER_URL,
    )

    workspace_gitea_token = obtain_api_token(
        token_name=WORKSPACE_SERVER_TOKEN_NAME,
        username=WORKSPACE_SERVER_USERNAME,
        password=WORKSPACE_SERVER_PASSWORD,
        gitea_url=WORKSPACE_SERVER_URL,
        scopes=["write:repository", "write:user"],
    )

    for repository_name in get_repositories(
        owner=MIRROR_SERVER_USERNAME,
        gitea_url=MIRROR_SERVER_URL,
        token=gitea_mirror_token,
    ):
        delete_repository(
            username=MIRROR_SERVER_USERNAME,
            gitea_url=MIRROR_SERVER_URL,
            repository_name=repository_name,
            token=gitea_mirror_token,
        )

    for repository_name in get_repositories(
        owner=WORKSPACE_SERVER_USERNAME,
        gitea_url=WORKSPACE_SERVER_URL,
        token=workspace_gitea_token,
    ):
        delete_repository(
            username=WORKSPACE_SERVER_USERNAME,
            gitea_url=WORKSPACE_SERVER_URL,
            repository_name=repository_name,
            token=workspace_gitea_token,
        )

    for repository in REPOSITORY_DATA["repositories"]:

        owner, repository_name = create_migration(
            repository_name=repository["repository_name"],
            repostiory_url=repository["repository_url"],
            repository_auth_token=repository["repository_auth_token"],
            gitea_url=MIRROR_SERVER_URL,
            token=gitea_mirror_token,
            service="github",  # TODO(cgavidia): Maybe this can be a parameter in config.
        )

        create_migration(
            repository_name=f"{repository['repository_name']}-mirror",
            repostiory_url=f"{MIRROR_SERVER_URL}/{owner}/{repository_name}",
            repository_auth_token=gitea_mirror_token,
            gitea_url=WORKSPACE_SERVER_URL,
            token=workspace_gitea_token,
            service="gitea",
        )


if __name__ == "__main__":
    main()
