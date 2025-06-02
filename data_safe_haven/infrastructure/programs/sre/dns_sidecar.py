from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_azure_native import (
    authorization,
    storage,
)

from data_safe_haven.functions import seeded_uuid
from data_safe_haven.infrastructure.components import FileShareFile, FileShareFileProps
from data_safe_haven.resources import resources_path
from data_safe_haven.utility import FileReader

# Configuration for the DNS Sidecar container.
CONTAINER_IMAGE: str = "mcr.microsoft.com/azure-cli:latest"
CONTAINER_NAME: str = "dnsmonitor"[:63]
INIT_COMMAND: tuple[str, str, str] = ("/bin/sh", "-c", "/mnt/init/init.sh")
CONTAINER_CPU: float = 0.5
CONTAINER_MEMORY: float = 0.5
MOUNT_PATH: str = "/mnt/init"

ENV_CONTAINER_GROUP: str = "CONTAINER_GROUP_NAME"
ENV_RESOURCE_GROUP: str = "RESOURCE_GROUP"
ENV_SUBSCRIPTION_ID: str = "SUBSCRIPTION_ID"
ENV_RECORD_NAME: str = "RECORD_NAME"
ENV_ZONE_NAME: str = "PRIVATE_ZONE_NAME"


class DnsSidecarProps:
    """Properties of the DnsMonitorProps"""

    def __init__(
        self,
        container_group_id: Input[str],
        dns_record_name: str,
        identity_principal_id: Input[str],
        private_record_set_id: Input[str],
        resource_group_name: Input[str],
        storage_account_name: Input[str],
        storage_account_key: Input[str],
    ):
        self.container_group_id = container_group_id
        self.dns_record_name = dns_record_name
        self.identity_principal_id = identity_principal_id
        self.private_record_set_id = private_record_set_id
        self.resource_group_name = resource_group_name
        self.storage_account_name = storage_account_name
        self.storage_account_key = storage_account_key


class DnsSidecarComponent(ComponentResource):

    def __init__(
        self,
        name: str,
        stack_name: str,
        props: DnsSidecarProps,
        opts: ResourceOptions | None = None,
    ):
        super().__init__("dsh:sre:DnsMonitorComponent", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        file_share_dns_monitor = storage.FileShare(
            f"{self._name}_file_share_{props.dns_record_name}_dnsmonitor",
            access_tier=storage.ShareAccessTier.TRANSACTION_OPTIMIZED,
            account_name=props.storage_account_name,
            resource_group_name=props.resource_group_name,
            share_name=f"{props.dns_record_name}-dnsmonitor",
            share_quota=1,
            signed_identifiers=[],
            opts=child_opts,
        )

        # Upload DNS Monitor Script
        dns_monitor_script_reader = FileReader(
            resources_path / "dns_monitor" / "init.sh"
        )

        self.file_share_dns_monitor_script = FileShareFile(
            f"{self._name}_file_share_{props.dns_record_name}_dnsmonitor_init",
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

        # Allowing the managed identity to update DNS Records
        dns_zone_role_definition = authorization.RoleDefinition(
            f"{self._name}_{props.dns_record_name}_dnsmonitor_dns_updater_role",
            role_name=f"DNS Zone updater for {props.dns_record_name} at {stack_name}",
            scope=props.private_record_set_id,
            description=f"Custom role for updating {props.dns_record_name}'s DNS records",
            permissions=[
                authorization.PermissionArgs(
                    actions=[
                        "Microsoft.Network/privateDnsZones/A/read",
                        "Microsoft.Network/privateDnsZones/A/write",
                    ],
                    not_actions=[],
                )
            ],
            assignable_scopes=[props.private_record_set_id],
        )

        authorization.RoleAssignment(
            f"{self._name}_dnsmonitor_dns_updater_role_assignment",
            principal_id=props.identity_principal_id,
            principal_type=authorization.PrincipalType.SERVICE_PRINCIPAL,
            role_assignment_name=str(
                seeded_uuid(f"{stack_name} DNS updater for {props.dns_record_name}")
            ),
            role_definition_id=dns_zone_role_definition.id,
            scope=props.private_record_set_id,
            opts=child_opts,
        )

        # Allowing the managed identity to retrieve the container group IP

        container_group_role_definition = authorization.RoleDefinition(
            f"{self._name}_dnsmonitor_ip_reader_role",
            role_name=f"Container group reader for {props.dns_record_name} at {stack_name}",
            scope=props.container_group_id,
            description=f"Custom role for reading {props.dns_record_name}'s container group",
            permissions=[
                authorization.PermissionArgs(
                    actions=[
                        "Microsoft.ContainerInstance/containerGroups/read",
                    ],
                    not_actions=[],
                )
            ],
            assignable_scopes=[props.container_group_id],
        )

        authorization.RoleAssignment(
            f"{self._name}_dnsmonitor_ip_reader_role_assignment",
            principal_id=props.identity_principal_id,
            principal_type=authorization.PrincipalType.SERVICE_PRINCIPAL,
            role_assignment_name=str(
                seeded_uuid(f"{stack_name} IP Reader for {props.dns_record_name}")
            ),
            role_definition_id=container_group_role_definition.id,
            scope=props.container_group_id,
            opts=child_opts,
        )
