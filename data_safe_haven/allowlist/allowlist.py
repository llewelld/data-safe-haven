from difflib import unified_diff
from typing import Self

from data_safe_haven.config import Context
from data_safe_haven.external import AzureSdk
from data_safe_haven.types import AllowlistRepository


class Allowlist:
    """Allowlist for packages"""

    @classmethod
    def from_remote(
        cls: type[Self],
        context: Context,
        *,
        repository: AllowlistRepository,
        sre_resource_group: str,
        storage_account_name: str,
    ) -> str:
        """Get the current package allowlist"""

        # Get the Azure SDK
        azure_sdk = AzureSdk(subscription_name=context.subscription_name)

        # Get the file share name
        file_share_name = "software-repositories-nexus-allowlists"
        if repository:
            file_share_file = f"{repository.value}.allowlist"

        # Get the allowlist file from the file share
        share_file = azure_sdk.download_share_file(
            file_share_file,
            sre_resource_group,
            storage_account_name,
            file_share_name,
        )
        return share_file

    @classmethod
    def remote_exists(
        cls: type[Self],
        context: Context,
        *,
        sre_resource_group: str,
        repository: AllowlistRepository,
        storage_account_name: str,
    ) -> bool:
        # Get the Azure SDK
        azure_sdk = AzureSdk(subscription_name=context.subscription_name)

        # Get the file share name
        file_share_name = "software-repositories-nexus-allowlists"
        file_name = f"{repository.value}.allowlist"
        share_list = azure_sdk.file_share_exists(
            file_name, sre_resource_group, storage_account_name, file_share_name
        )
        return share_list

    @classmethod
    def upload(
        cls: type[Self],
        context: Context,
        *,
        storage_account_name: str,
        sre_resource_group: str,
        repository: AllowlistRepository,
        allowlist: str,
    ) -> None:
        # Get the Azure SDK
        azure_sdk = AzureSdk(subscription_name=context.subscription_name)
        file_share_name = "software-repositories-nexus-allowlists"
        file_name = f"{repository.value}.allowlist"

        azure_sdk.upload_file_share(
            allowlist,
            file_name,
            sre_resource_group,
            storage_account_name,
            file_share_name,
        )

    @classmethod
    def remote_diff(
        cls: type[Self],
        context: Context,
        *,
        sre_resource_group: str,
        storage_account_name: str,
        repository: AllowlistRepository,
        allowlist: str,
    ) -> list[str]:
        # Get the Azure SDK
        azure_sdk = AzureSdk(subscription_name=context.subscription_name)

        # Get the file share name
        file_share_name = "software-repositories-nexus-allowlists"
        file_name = f"{repository.value}.allowlist"

        remote_allowlist = azure_sdk.download_share_file(
            file_name,
            sre_resource_group,
            storage_account_name,
            file_share_name,
        )

        # Get the diff
        diff = list(
            unified_diff(
                remote_allowlist.splitlines(),
                allowlist.splitlines(),
                fromfile="remote",
                tofile="local",
            )
        )
        return diff
