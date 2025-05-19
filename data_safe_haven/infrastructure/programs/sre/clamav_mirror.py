from collections.abc import Mapping

from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_azure_native import containerinstance, network, storage

from data_safe_haven.infrastructure.common import (
    DockerHubCredentials,
    get_id_from_subnet,
    get_ip_address_from_container_group,
)
from data_safe_haven.infrastructure.components import (
    FileShareFile,
    LocalDnsRecordComponent,
    LocalDnsRecordProps,
    WrappedLogAnalyticsWorkspace,
)
from data_safe_haven.infrastructure.programs.sre.dns_monitor import (
    DnsMonitorComponent,
)


class SREClamAVMirrorProps:
    """Properties for SREClamAVMirrorComponent"""

    def __init__(
        self,
        dns_monitor_identity_id: Input[str],
        dns_monitor_file_share_script: Input[FileShareFile],
        dns_server_ip: Input[str],
        dockerhub_credentials: DockerHubCredentials,
        location: Input[str],
        log_analytics_workspace: Input[WrappedLogAnalyticsWorkspace],
        resource_group_name: Input[str],
        sre_fqdn: Input[str],
        storage_account_key: Input[str],
        storage_account_name: Input[str],
        subnet: Input[network.GetSubnetResult],
        subscription_id: Input[str],
    ) -> None:
        self.dns_monitor_identity_id = dns_monitor_identity_id
        self.dns_monitor_file_share_script = dns_monitor_file_share_script
        self.dns_server_ip = dns_server_ip
        self.dockerhub_credentials = dockerhub_credentials
        self.location = location
        self.log_analytics_workspace = log_analytics_workspace
        self.resource_group_name = resource_group_name
        self.sre_fqdn = sre_fqdn
        self.storage_account_key = storage_account_key
        self.storage_account_name = storage_account_name
        self.subnet_id = Output.from_input(subnet).apply(get_id_from_subnet)
        self.subscription_id = subscription_id


class SREClamAVMirrorComponent(ComponentResource):
    """Deploy ClamAV mirror with Pulumi"""

    def __init__(
        self,
        name: str,
        stack_name: str,
        props: SREClamAVMirrorProps,
        opts: ResourceOptions | None = None,
        tags: Input[Mapping[str, Input[str]]] | None = None,
    ) -> None:
        super().__init__("dsh:sre:ClamAVMirrorComponent", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))
        child_tags = tags if tags else {}

        # Define configuration file shares
        file_share_clamav_mirror = storage.FileShare(
            f"{self._name}_file_share_clamav_mirror",
            access_tier=storage.ShareAccessTier.TRANSACTION_OPTIMIZED,
            account_name=props.storage_account_name,
            resource_group_name=props.resource_group_name,
            share_name="clamav-mirror",
            share_quota=2,
            signed_identifiers=[],
            opts=child_opts,
        )

        # Define the container group with ClamAV
        container_group_name = f"{stack_name}-container-group-clamav"
        dns_record_name = "apt"
        container_group = containerinstance.ContainerGroup(
            f"{self._name}_container_group",
            container_group_name=container_group_name,
            containers=[
                containerinstance.ContainerArgs(
                    image=DnsMonitorComponent.sidecar_container_image,
                    name=DnsMonitorComponent.sidecar_container_name,
                    command=DnsMonitorComponent.sidecar_command,
                    resources=containerinstance.ResourceRequirementsArgs(
                        requests=containerinstance.ResourceRequestsArgs(
                            cpu=DnsMonitorComponent.sidecar_container_cpu,
                            memory_in_gb=DnsMonitorComponent.sidecar_container_memory_in_gb,
                        ),
                    ),
                    environment_variables=[
                        containerinstance.EnvironmentVariableArgs(
                            name="CONTAINER_GROUP_NAME",
                            value=container_group_name,
                        ),
                        containerinstance.EnvironmentVariableArgs(
                            name="RESOURCE_GROUP", value=props.resource_group_name
                        ),
                        containerinstance.EnvironmentVariableArgs(
                            name="SUBSCRIPTION_ID",
                            value=props.subscription_id,
                        ),
                        containerinstance.EnvironmentVariableArgs(
                            name="RECORD_NAME",
                            value=dns_record_name,
                        ),
                        containerinstance.EnvironmentVariableArgs(
                            name="PRIVATE_ZONE_NAME",
                            value=Output.concat("privatelink.", props.sre_fqdn),
                        ),
                    ],
                    volume_mounts=[
                        containerinstance.VolumeMountArgs(
                            mount_path=DnsMonitorComponent.sidecar_container_mount_path,
                            name=DnsMonitorComponent.share_name,
                            read_only=True,
                        )
                    ],
                ),
                containerinstance.ContainerArgs(
                    image="chmey/clamav-mirror:latest",  # only one image is published
                    name="clamav-mirror"[:63],
                    environment_variables=[],
                    ports=[
                        containerinstance.ContainerPortArgs(
                            port=80,
                            protocol=containerinstance.ContainerGroupNetworkProtocol.TCP,
                        ),
                    ],
                    resources=containerinstance.ResourceRequirementsArgs(
                        requests=containerinstance.ResourceRequestsArgs(
                            cpu=2,
                            memory_in_gb=2,
                        ),
                    ),
                    volume_mounts=[
                        containerinstance.VolumeMountArgs(
                            mount_path="/clamav",
                            name="clamavmirror-clamavmirror-clamav",
                            read_only=False,
                        ),
                    ],
                ),
            ],
            diagnostics=containerinstance.ContainerGroupDiagnosticsArgs(
                log_analytics=containerinstance.LogAnalyticsArgs(
                    workspace_id=props.log_analytics_workspace.workspace_id,
                    workspace_key=props.log_analytics_workspace.workspace_key,
                ),
            ),
            dns_config=containerinstance.DnsConfigurationArgs(
                name_servers=[props.dns_server_ip],
            ),
            identity=containerinstance.ContainerGroupIdentityArgs(
                user_assigned_identities=[props.dns_monitor_identity_id],
                type=containerinstance.ResourceIdentityType.USER_ASSIGNED,
            ),
            # Required due to DockerHub rate-limit: https://docs.docker.com/docker-hub/download-rate-limit/
            image_registry_credentials=[
                {
                    "password": Output.secret(props.dockerhub_credentials.access_token),
                    "server": props.dockerhub_credentials.server,
                    "username": props.dockerhub_credentials.username,
                }
            ],
            ip_address=containerinstance.IpAddressArgs(
                ports=[
                    containerinstance.PortArgs(
                        port=80,
                        protocol=containerinstance.ContainerGroupNetworkProtocol.TCP,
                    )
                ],
                type=containerinstance.ContainerGroupIpAddressType.PRIVATE,
            ),
            location=props.location,
            os_type=containerinstance.OperatingSystemTypes.LINUX,
            resource_group_name=props.resource_group_name,
            restart_policy=containerinstance.ContainerGroupRestartPolicy.ALWAYS,
            sku=containerinstance.ContainerGroupSku.STANDARD,
            subnet_ids=[
                containerinstance.ContainerGroupSubnetIdArgs(id=props.subnet_id),
            ],
            volumes=[
                containerinstance.VolumeArgs(
                    azure_file=containerinstance.AzureFileVolumeArgs(
                        share_name=file_share_clamav_mirror.name,
                        storage_account_key=props.storage_account_key,
                        storage_account_name=props.storage_account_name,
                    ),
                    name="clamavmirror-clamavmirror-clamav",
                ),
                containerinstance.VolumeArgs(
                    azure_file=containerinstance.AzureFileVolumeArgs(
                        share_name=DnsMonitorComponent.share_name,
                        storage_account_key=props.storage_account_key,
                        storage_account_name=props.storage_account_name,
                    ),
                    name=DnsMonitorComponent.share_name,
                ),
            ],
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    delete_before_replace=True,
                    replace_on_changes=["containers"],
                ),
            ),
            tags=child_tags,
        )

        # Register the container group in the SRE DNS zone
        local_dns = LocalDnsRecordComponent(
            f"{self._name}_clamav_mirror_dns_record_set",
            LocalDnsRecordProps(
                base_fqdn=props.sre_fqdn,
                private_ip_address=get_ip_address_from_container_group(container_group),
                record_name="clamav",
                resource_group_name=props.resource_group_name,
            ),
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(parent=container_group)
            ),
        )

        # Register outputs
        self.hostname = local_dns.hostname
