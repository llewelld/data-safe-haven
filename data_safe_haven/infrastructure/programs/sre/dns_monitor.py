from collections.abc import Mapping
from typing import ClassVar

from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_azure_native import (
    authorization,
    managedidentity,
    storage,
)

from data_safe_haven.functions import seeded_uuid
from data_safe_haven.infrastructure.components import FileShareFile, FileShareFileProps
from data_safe_haven.resources import resources_path
from data_safe_haven.utility import FileReader


class DnsMonitorProps:
    """Properties of the DnsMonitorProps"""

    def __init__(
        self,
        location: Input[str],
        resource_group_id: Input[str],
        resource_group_name: Input[str],
        storage_account_name: Input[str],
        storage_account_key: Input[str],
        subscription_id: Input[str],
    ):
        self.location = location
        self.resource_group_id = resource_group_id
        self.resource_group_name = resource_group_name
        self.storage_account_name = storage_account_name
        self.storage_account_key = storage_account_key
        self.subscription_id = subscription_id


class DnsMonitorComponent(ComponentResource):

    azure_role_ids: ClassVar[dict[str, str]] = {
        "Private DNS Zone Contributor": "b12aa53e-6015-4669-85d0-8515ebb3ae7f",
        "Azure Container Instances Contributor Role": "5d977122-f97e-4b4d-a52f-6b43003ddb4d",
    }

    share_name: ClassVar[str] = "dns-monitor"

    sidecar_container_image: ClassVar[str] = "mcr.microsoft.com/azure-cli:latest"
    sidecar_container_name: ClassVar[str] = "dnsmonitor"[:63]
    sidecar_command: ClassVar[list[str]] = ["/bin/sh", "-c", "/mnt/init/init.sh"]
    sidecar_container_cpu: ClassVar[float] = 0.5
    sidecar_container_memory_in_gb: ClassVar[float] = 0.5
    sidecar_container_mount_path: ClassVar[str] = "/mnt/init"

    container_group_environment_variable: ClassVar[str] = "CONTAINER_GROUP_NAME"
    resource_group_environment_variable: ClassVar[str] = "RESOURCE_GROUP"
    subscription_id_environment_variable: ClassVar[str] = "SUBSCRIPTION_ID"
    record_name_environment_variable: ClassVar[str] = "RECORD_NAME"
    zone_name_environment_variable: ClassVar[str] = "PRIVATE_ZONE_NAME"

    def __init__(
        self,
        name: str,
        stack_name: str,
        props: DnsMonitorProps,
        opts: ResourceOptions | None = None,
        tags: Input[Mapping[str, Input[str]]] | None = None,
    ):
        super().__init__("dsh:sre:DnsMonitorComponent", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))
        child_tags = {"component": "Dns monitor"} | (tags if tags else {})

        file_share_dns_monitor = storage.FileShare(
            f"{self._name}_file_share_dns_monitor",
            access_tier=storage.ShareAccessTier.TRANSACTION_OPTIMIZED,
            account_name=props.storage_account_name,
            resource_group_name=props.resource_group_name,
            share_name=self.share_name,
            share_quota=1,
            signed_identifiers=[],
            opts=child_opts,
        )

        # Upload DNS Monitor Script
        dns_monitor_script_reader = FileReader(
            resources_path / "dns_monitor" / "init.sh"
        )

        self.file_share_dns_monitor_script = FileShareFile(
            f"{self._name}_file_share_dns_monitor_script",
            FileShareFileProps(
                destination_path=dns_monitor_script_reader.name,
                share_name=file_share_dns_monitor.name,
                file_contents=Output.secret(dns_monitor_script_reader.file_contents()),
                storage_account_key=props.storage_account_key,
                storage_account_name=props.storage_account_name,
            ),
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(parent=file_share_dns_monitor)
            ),
        )

        # Define DNS Monitor Identity
        self.identity_dns_monitor = managedidentity.UserAssignedIdentity(
            f"{self._name}_id_dns_monitor",
            location=props.location,
            resource_group_name=props.resource_group_name,
            resource_name_=f"{stack_name}-id-dns-monitor",
            opts=child_opts,
            tags=child_tags,
        )

        # Grant "Private DNS Zone Contributor" permissions to the Service Principal.
        authorization.RoleAssignment(
            f"{self._name}_dns_monitor_dns_zone_contributor_role_assignment",
            principal_id=self.identity_dns_monitor.principal_id,
            principal_type=authorization.PrincipalType.SERVICE_PRINCIPAL,
            role_assignment_name=str(
                seeded_uuid(f"{stack_name} Private DNS Zone Contributor")
            ),
            role_definition_id=Output.concat(
                "/subscriptions/",
                props.subscription_id,
                "/providers/Microsoft.Authorization/roleDefinitions/",
                self.azure_role_ids["Private DNS Zone Contributor"],
            ),
            scope=props.resource_group_id,
            opts=child_opts,
        )

        # Grant "Azure Container Instances Contributor" permissions to the Service Principal.
        authorization.RoleAssignment(
            f"{self._name}_dns_monitor_container_instance_contributor_role_assignment",
            principal_id=self.identity_dns_monitor.principal_id,
            principal_type=authorization.PrincipalType.SERVICE_PRINCIPAL,
            role_assignment_name=str(
                seeded_uuid(f"{stack_name} Azure Container Instances Contributor")
            ),
            role_definition_id=Output.concat(
                "/subscriptions/",
                props.subscription_id,
                "/providers/Microsoft.Authorization/roleDefinitions/",
                self.azure_role_ids["Azure Container Instances Contributor Role"],
            ),
            scope=props.resource_group_id,
            opts=child_opts,
        )
