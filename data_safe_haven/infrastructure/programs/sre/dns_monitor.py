from collections.abc import Mapping

from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_azure_native import (
    authorization,
    containerinstance,
    managedidentity,
    storage,
)

from data_safe_haven.functions import seeded_uuid
from data_safe_haven.infrastructure.components import FileShareFile, FileShareFileProps
from data_safe_haven.resources import resources_path
from data_safe_haven.utility import FileReader

# TODO(cgavidia): This needs adjustments. Some components needs to be instantiated once, other multiple times.


class DnsMonitorProps:
    """Properties of the DnsMonitorProps"""

    def __init__(
        self,
        location: Input[str],
        resource_group_name: Input[str],
        storage_account_name: Input[str],
        storage_account_key: Input[str],
        subscription_id: Input[str],
    ):
        self.location = location
        self.resource_group_name = resource_group_name
        self.storage_account_name = storage_account_name
        self.storage_account_key = storage_account_key
        self.subscription_id = subscription_id


class DnsMonitorComponent(ComponentResource):

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
            share_name="dns-monitor",
            share_quota=1,
            signed_identifiers=[],
            opts=child_opts,
        )

        # Upload DNS Monitor Script
        dns_monitor_script_reader = FileReader(
            resources_path / "dns_monitor" / "init.sh"
        )

        self.file_share_gitea_dns_monitor_script = FileShareFile(
            f"{self._name}_file_share_gitea_dns_monitor_script",
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
            resource_name_=f"{stack_name}-id-key-vault-reader",
            opts=child_opts,
            tags=child_tags,
        )

        # Grant "Contributor" permissions to the Service Principal.
        authorization.RoleAssignment(
            f"{self._name}_dns_monitor_contributor_role_assignment",
            principal_id=self.identity_dns_monitor.principal_id,
            principal_type=authorization.PrincipalType.SERVICE_PRINCIPAL,
            role_assignment_name=str(
                seeded_uuid(f"{stack_name} DNS Monitor Contributor")
            ),
            role_definition_id=Output.concat(
                "/subscriptions/",
                props.subscription_id,
                "/providers/Microsoft.Authorization/roleDefinitions/",
                self.azure_role_ids["Contributor"],
            ),
            scope=f"subscriptions/{props.subscription_id}",  # TODO(cgavidia): Only for testing!
            opts=child_opts,
        )

    def get_container_arguments(self):
        return (
            containerinstance.ContainerArgs(
                image="mcr.microsoft.com/azure-cli:latest",
                name="dnsmonitor"[:63],
                command=["/bin/sh", "-c", "/mnt/init/init.sh"],
                resources=containerinstance.ResourceRequirementsArgs(
                    requests=containerinstance.ResourceRequestsArgs(
                        cpu=0.5,
                        memory_in_gb=0.5,
                    ),
                ),
                environment_variables=[],
                volume_mounts=[
                    containerinstance.VolumeMountArgs(
                        mount_path="/mnt/init",
                        name="dns-monitor",
                        read_only=True,
                    )
                ],
            ),
        )

    def get_group_identity(self):
        return containerinstance.ContainerGroupIdentityArgs(
            user_assigned_identities=[self.identity_dns_monitor.id],
            type=containerinstance.ResourceIdentityType.USER_ASSIGNED,
        )
