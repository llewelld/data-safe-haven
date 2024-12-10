from typing import TypeVar

from data_safe_haven.config import DSHPulumiConfig, SREConfig
from data_safe_haven.external import AzureSdk
from data_safe_haven.infrastructure import SREProjectManager
from data_safe_haven.serialisers import ContextBase

T = TypeVar("T", bound="Allowlist")


class SREAllowlist:
    """Allowlist for packages"""

    def from_remote(
        self: T,
        context: ContextBase,
        *,
        pulumi_config: DSHPulumiConfig,
        repository: str,
        sre_config: SREConfig,
    ) -> str:
        """Get the current package allowlist"""

        # Get the Azure SDK
        azure_sdk = AzureSdk(subscription_name=context.subscription_name)

        sre_stack = SREProjectManager(
            context=context,
            config=sre_config,
            pulumi_config=pulumi_config,
        )

        # Get the storage account name
        storage_account_name = sre_stack.output("data")[
            "storage_account_data_configuration_name"
        ]
        sre_resource_group = f"{sre_stack.stack_name}-rg"
        # Get the file share name
        file_share_name = "software-repositories-nexus-allowlists"
        if repository:
            file_share_file = f"{repository}.allowlist"

        # Get the allowlist file from the file share
        share_file = azure_sdk.download_share_file(
            file_share_file,
            sre_resource_group,
            storage_account_name,
            file_share_name,
        )
        return share_file
