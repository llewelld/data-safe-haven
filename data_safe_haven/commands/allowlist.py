"""Command group for managing package allowlists"""

from pathlib import Path
from typing import Annotated, Optional

import typer

from data_safe_haven import console
from data_safe_haven.allowlist import SREAllowlist
from data_safe_haven.config import ContextManager, DSHPulumiConfig, SREConfig
from data_safe_haven.exceptions import DataSafeHavenConfigError, DataSafeHavenError
from data_safe_haven.logging import get_logger
from data_safe_haven.types import AllowlistRepository

allowlist_command_group = typer.Typer()


@allowlist_command_group.command()
def show(
    sre: Annotated[
        str,
        typer.Argument(help="Name of SRE to show allowlist for."),
    ],
    repository: Annotated[
        AllowlistRepository,
        typer.Argument(help="Name of the repository to show the allowlist for."),
    ],
    file: Annotated[
        Optional[str],  # noqa: UP007
        typer.Option(help="File path to write the allowlist to."),
    ] = None,
) -> None:
    """Print the current package allowlist"""
    logger = get_logger()

    try:
        context = ContextManager.from_file().assert_context()
    except DataSafeHavenConfigError as exc:
        logger.critical(
            "No context is selected. Use `dsh context add` to create a context "
            "or `dsh context switch` to select one."
        )
        raise typer.Exit(1) from exc

    sre_config = SREConfig.from_remote_by_name(context, sre)

    # Load Pulumi config
    pulumi_config = DSHPulumiConfig.from_remote(context)

    if sre_config.name not in pulumi_config.project_names:
        msg = f"Could not load Pulumi settings for '{sre_config.name}'. Have you deployed the SRE?"
        logger.error(msg)
        raise typer.Exit(1)

    try:
        allow_list = SREAllowlist.from_remote(
            context=context,
            pulumi_config=pulumi_config,
            repository=repository,
            sre_config=sre_config,
        )
    except DataSafeHavenError as exc:
        logger.critical(
            "No allowlist is configured. Use `dsh allowlist upload` to create one."
        )
        raise typer.Exit(1) from exc

    if file:
        with open(file, "w") as f:
            f.write(allow_list)
    else:
        console.print(allow_list)


@allowlist_command_group.command()
def upload(
    sre: Annotated[
        str,
        typer.Argument(help="Name of SRE to upload the allowlist for."),
    ],
    file: Annotated[
        Path,
        typer.Argument(help="Path to the allowlist file to upload."),
    ],
    repository: Annotated[
        AllowlistRepository,
        typer.Argument(help="Name of the repository to upload the allowlist for."),
    ],
    force: Annotated[  # noqa: FBT002
        bool,
        typer.Option(help="Skip check for existing remote allowlist."),
    ] = False,
) -> None:
    """Upload a package allowlist"""
    context = ContextManager.from_file().assert_context()
    logger = get_logger()

    if file.is_file():
        with open(file) as f:
            allowlist = f.read()
    else:
        logger.critical(f"Allowlist file '{file}' not found.")
        raise typer.Exit(1)
    sre_config = SREConfig.from_remote_by_name(context, sre)

    # Load Pulumi config
    pulumi_config = DSHPulumiConfig.from_remote(context)

    if sre_config.name not in pulumi_config.project_names:
        msg = f"Could not load Pulumi settings for '{sre_config.name}'. Have you deployed the SRE?"
        logger.error(msg)
        raise typer.Exit(1)

    if not force and SREAllowlist.remote_exists(
        context=context,
        sre_config=sre_config,
        pulumi_config=pulumi_config,
        repository=repository,
    ):
        if not console.confirm(
            f"An allowlist already exists for {repository.name}. Do you want to overwrite it?",
            default_to_yes=True,
        ):
            raise typer.Exit()

    try:
        SREAllowlist.upload(
            context=context,
            sre_config=sre_config,
            pulumi_config=pulumi_config,
            repository=repository,
            allowlist=allowlist,
        )
    except DataSafeHavenError as exc:
        logger.error(f"Failed to upload allowlist: {exc}")
        raise typer.Exit(1) from exc
