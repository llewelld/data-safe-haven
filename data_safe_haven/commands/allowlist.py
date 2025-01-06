"""Command group for managing package allowlists"""

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
        allow_list = SREAllowlist().from_remote(
            context=context,
            pulumi_config=pulumi_config,
            repository=repository,
            sre_config=sre_config,
        )
    except DataSafeHavenError as exc:
        logger.critical(
            "No allowlist is configured. Use `dsh allowlist add` to create one."
        )
        raise typer.Exit(1) from exc

    if file:
        with open(file, "w") as f:
            f.write(allow_list)
    else:
        console.print(allow_list)


@allowlist_command_group.command()
def upload(
    file: Annotated[
        str,
        typer.Argument(help="Path to the allowlist file to upload."),
    ],
    repository: Annotated[
        str,  # noqa: UP007
        typer.Argument(help="Name of the repository to upload the allowlist for."),
    ] = None,
) -> None:
    """Upload a package allowlist"""
    pass
