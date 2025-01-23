"""Command group for managing package allowlists"""

from pathlib import Path
from typing import Annotated, Optional

import typer

from data_safe_haven import console
from data_safe_haven.allowlist import Allowlist
from data_safe_haven.config import ContextManager, DSHPulumiConfig, SREConfig
from data_safe_haven.exceptions import DataSafeHavenConfigError, DataSafeHavenError
from data_safe_haven.infrastructure import SREProjectManager
from data_safe_haven.logging import get_logger
from data_safe_haven.types import AllowlistRepository

allowlist_command_group = typer.Typer()


@allowlist_command_group.command()
def show(
    name: Annotated[
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

    sre_config = SREConfig.from_remote_by_name(context, name)

    # Load Pulumi config
    pulumi_config = DSHPulumiConfig.from_remote(context)

    if sre_config.name not in pulumi_config.project_names:
        msg = f"Could not load Pulumi settings for '{sre_config.name}'. Have you deployed the SRE?"
        logger.error(msg)
        raise typer.Exit(1)

    sre_stack = SREProjectManager(
        context=context,
        config=sre_config,
        pulumi_config=pulumi_config,
    )

    allowlist_storage_account = sre_stack.output("data")[
        "storage_account_data_configuration_name"
    ]

    try:
        allow_list = Allowlist.from_remote(
            context=context,
            repository=repository,
            storage_account_name=allowlist_storage_account,
            sre_resource_group=sre_stack.output("sre_resource_group"),
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
def template(
    repository: Annotated[
        AllowlistRepository,
        typer.Argument(help="Name of the repository to show the allowlist for."),
    ],
    file: Annotated[
        Optional[Path],  # noqa: UP007
        typer.Option(help="File path to write allowlist template to."),
    ] = None,
) -> None:
    """Print a template for the package allowlist"""

    template_path = Path(
        "data_safe_haven/resources",
        "software_repositories",
        "allowlists",
        f"{repository.value}.allowlist",
    )
    with open(template_path) as f:
        example_allowlist = f.read()
    if file:
        with open(file, "w") as f:
            f.write(example_allowlist)
        raise typer.Exit()
    else:
        console.print(example_allowlist)


@allowlist_command_group.command()
def upload(
    name: Annotated[
        str,
        typer.Argument(help="Name of SRE to upload the allowlist for."),
    ],
    file: Annotated[
        Path,
        typer.Argument(help="Path to the allowlist file to upload."),
    ],
    repository: Annotated[
        AllowlistRepository,
        typer.Argument(help="Repository type of the allowlist."),
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
    sre_config = SREConfig.from_remote_by_name(context, name)

    # Load Pulumi config
    pulumi_config = DSHPulumiConfig.from_remote(context)

    if sre_config.name not in pulumi_config.project_names:
        msg = f"Could not load Pulumi settings for '{sre_config.name}'. Have you deployed the SRE?"
        logger.error(msg)
        raise typer.Exit(1)

    sre_stack = SREProjectManager(
        context=context,
        config=sre_config,
        pulumi_config=pulumi_config,
    )

    sre_resource_group = sre_stack.output("sre_resource_group")
    allowlist_storage_account = sre_stack.output("data")[
        "storage_account_data_configuration_name"
    ]

    if not force and Allowlist.remote_exists(
        context=context,
        sre_resource_group=sre_resource_group,
        storage_account_name=allowlist_storage_account,
        repository=repository,
    ):
        if diff := Allowlist.remote_diff(
            context=context,
            sre_resource_group=sre_resource_group,
            storage_account_name=allowlist_storage_account,
            repository=repository,
            allowlist=allowlist,
        ):
            for line in list(filter(None, "\n".join(diff).splitlines())):
                logger.info(line)
            if not console.confirm(
                f"An allowlist already exists for {repository.name}. Do you want to overwrite it?",
                default_to_yes=True,
            ):
                raise typer.Exit()
        else:
            console.print("No changes, won't upload allowlist.")
            raise typer.Exit()
    try:
        logger.info(f"Uploading allowlist for {repository.name} to {sre_config.name}")
        Allowlist.upload(
            context=context,
            sre_resource_group=sre_resource_group,
            storage_account_name=allowlist_storage_account,
            repository=repository,
            allowlist=allowlist,
        )
    except DataSafeHavenError as exc:
        logger.error(f"Failed to upload allowlist: {exc}")
        raise typer.Exit(1) from exc
