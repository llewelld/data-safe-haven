from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_azure_native import app, authorization, storage

from data_safe_haven.functions import b64encode, seeded_uuid
from data_safe_haven.infrastructure.components import (
    FileShareFile,
    FileShareFileProps,
    WrappedLogAnalyticsWorkspace,
)
from data_safe_haven.resources import resources_path
from data_safe_haven.utility import FileReader

# Configuration for the DNS Sidecar container.
CONTAINER_NAME: str = "dnsmonitor"  # must be fewer than 64 characters
INIT_COMMAND: tuple[str, str] = ("/bin/sh", "/mnt/init/init.sh")
CONTAINER_CPU: float = 0.25
CONTAINER_MEMORY: float = 0.5
MOUNT_PATH: str = "/mnt/init"
INIT_SCRIPT_CONTENT: str = b64encode(
    FileReader(resources_path / "dns_monitor" / "init.sh").file_contents()
)  # DNS Monitor Script


class DnsSidecarProps:
    """Properties of the DnsMonitorProps"""

    def __init__(
        self,
        container_group_id: Input[str],
        dns_record_name: str,
        identity_principal_id: Input[str],
        location: Input[str],
        log_analytics_workspace: Input[WrappedLogAnalyticsWorkspace],
        private_record_set_id: Input[str],
        resource_group_name: Input[str],
        sre_fqdn: Input[str],
        subscription_id: Input[str],
        storage_account_name: Input[str],
        storage_account_key: Input[str],
    ):
        self.container_group_id = container_group_id
        self.dns_record_name = dns_record_name
        self.identity_principal_id = identity_principal_id
        self.location = location
        self.log_analytics_workspace = log_analytics_workspace
        self.private_record_set_id = private_record_set_id
        self.resource_group_name = resource_group_name
        self.sre_fqdn = sre_fqdn
        self.subscription_id = subscription_id
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

        # TODO: Experimenting with Container App Jobs:
        self.container_app_job = DnsSidecarContainerAppJob(
            f"{self._name}_app_job", stack_name, props, opts
        )


class DnsSidecarContainerAppJob(ComponentResource):

    def __init__(
        self,
        name: str,
        stack_name: str,
        props: DnsSidecarProps | None = None,
        opts: ResourceOptions | None = None,
    ) -> None:
        super().__init__("dsh:sre:DnsSidecarContainerAppJob", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        if props is not None:

            file_share = storage.FileShare(
                f"{self._name}_file_share_{props.dns_record_name}_dnsmonitor",
                access_tier=storage.ShareAccessTier.TRANSACTION_OPTIMIZED,
                account_name=props.storage_account_name,
                resource_group_name=props.resource_group_name,
                share_name=f"{props.dns_record_name}-dnsmonitor-share",
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
                    share_name=file_share.name,
                    file_contents=Output.secret(
                        dns_monitor_script_reader.file_contents()
                    ),
                    storage_account_key=props.storage_account_key,
                    storage_account_name=props.storage_account_name,
                ),
                opts=ResourceOptions.merge(
                    child_opts, ResourceOptions(parent=file_share)
                ),
            )

            # TODO: We can pass the workspace id and key via props.
            managed_environment = app.ManagedEnvironment(
                f"env-jobs-{props.dns_record_name}",
                app_logs_configuration=app.AppLogsConfigurationArgs(
                    destination="log-analytics",
                    log_analytics_configuration=app.LogAnalyticsConfigurationArgs(
                        customer_id=props.log_analytics_workspace.workspace_id,
                        shared_key=props.log_analytics_workspace.workspace_key,
                    ),
                ),
                resource_group_name=props.resource_group_name,
                location=props.location,
                opts=child_opts,
            )

            managed_environment_storage = app.ManagedEnvironmentsStorage(
                f"env-storage-{props.dns_record_name}",
                environment_name=managed_environment.name,
                resource_group_name=props.resource_group_name,
                properties=app.ManagedEnvironmentStoragePropertiesArgs(
                    azure_file=app.AzureFilePropertiesArgs(
                        access_mode=app.AccessMode.READ_ONLY,
                        account_key=props.storage_account_key,
                        account_name=props.storage_account_name,
                        share_name=file_share.name,
                    )
                ),
            )

            volume_name: str = f"{props.dns_record_name}-dnsmonitor-volume"
            self.job = app.Job(
                f"job-{props.dns_record_name}",
                resource_group_name=props.resource_group_name,
                environment_id=managed_environment.id,
                configuration=app.JobConfigurationArgs(
                    trigger_type=app.TriggerType.SCHEDULE,
                    replica_timeout=1800,
                    schedule_trigger_config=app.JobConfigurationScheduleTriggerConfigArgs(
                        cron_expression="*/1 * * * *"
                    ),
                ),
                template=app.JobTemplateArgs(
                    containers=[
                        app.ContainerArgs(
                            image="mcr.microsoft.com/azure-cli:2.74.0",
                            name=CONTAINER_NAME,
                            command=INIT_COMMAND,
                            resources=app.ContainerResourcesArgs(
                                cpu=CONTAINER_CPU,
                                memory=f"{CONTAINER_MEMORY}Gi",
                            ),
                            env=[
                                app.EnvironmentVarArgs(
                                    name="CONTAINER_GROUP_NAME",
                                    value=f"{stack_name}-container-group-{props.dns_record_name}",
                                ),
                                app.EnvironmentVarArgs(
                                    name="RESOURCE_GROUP",
                                    value=props.resource_group_name,
                                ),
                                app.EnvironmentVarArgs(
                                    name="SUBSCRIPTION_ID",
                                    value=props.subscription_id,
                                ),
                                app.EnvironmentVarArgs(
                                    name="RECORD_NAME",
                                    value=props.dns_record_name,
                                ),
                                app.EnvironmentVarArgs(
                                    name="PRIVATE_ZONE_NAME",
                                    value=Output.concat("privatelink.", props.sre_fqdn),
                                ),
                            ],
                            volume_mounts=[
                                app.VolumeMountArgs(
                                    mount_path=MOUNT_PATH,
                                    volume_name=volume_name,
                                )
                            ],
                        )
                    ],
                    volumes=[
                        app.VolumeArgs(
                            name=volume_name,
                            storage_type=app.StorageType.AZURE_FILE,
                            storage_name=managed_environment_storage.name,
                        )
                    ],
                ),
            )
