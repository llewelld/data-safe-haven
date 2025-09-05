from collections.abc import Mapping

from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_azure_native import containerinstance, storage

from data_safe_haven.infrastructure.common import DockerHubCredentials
from data_safe_haven.infrastructure.components import (
    FileShareFile,
    FileShareFileProps,
    WrappedLogAnalyticsWorkspace,
)
from data_safe_haven.resources import resources_path
from data_safe_haven.utility import FileReader


class SREGiteMirrorManagerProps:
    """Properties for SREGiteMirrorManagerComponent"""

    def __init__(
        self,
        dns_server_ip: Input[str],
        dockerhub_credentials: DockerHubCredentials,
        location: Input[str],
        log_analytics_workspace: Input[WrappedLogAnalyticsWorkspace],
        mirror_manager_subnet_id: Input[str],
        resource_group_name: Input[str],
        storage_account_key: Input[str],
        storage_account_name: Input[str],
    ) -> None:
        self.dns_server_ip = dns_server_ip
        self.dockerhub_credentials = dockerhub_credentials
        self.location = location
        self.log_analytics_workspace = log_analytics_workspace
        self.mirror_manager_subnet_id = mirror_manager_subnet_id
        self.resource_group_name = resource_group_name
        self.storage_account_key = storage_account_key
        self.storage_account_name = storage_account_name


class SREGiteMirrorManagerComponent(ComponentResource):
    def __init__(
        self,
        name: str,
        stack_name: str,
        props: SREGiteMirrorManagerProps,
        opts: ResourceOptions | None = None,
        tags: Input[Mapping[str, Input[str]]] | None = None,
    ) -> None:
        super().__init__("dsh:sre:GiteaServerComponent", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))
        child_tags = {"component": "Gitea server"} | (tags if tags else {})  # type: ignore

        # Define configuration file shares
        file_share_mirror_manager = storage.FileShare(
            f"{self._name}_file_share_mirror_manager",
            access_tier=storage.ShareAccessTier.TRANSACTION_OPTIMIZED,
            account_name=props.storage_account_name,
            resource_group_name=props.resource_group_name,
            share_name="mirror-manager",
            share_quota=1,
            signed_identifiers=[],
            opts=child_opts,
        )

        # Upload Python script file
        python_script_reader = FileReader(
            resources_path / "mirror_manager" / "mirrors.py"
        )

        file_share_mirror_manager_python_script = FileShareFile(
            f"{self._name}_file_share_gitea_caddy_caddyfile",
            FileShareFileProps(
                destination_path=python_script_reader.name,
                share_name=file_share_mirror_manager.name,
                file_contents=Output.secret(python_script_reader.file_contents()),
                storage_account_key=props.storage_account_key,
                storage_account_name=props.storage_account_name,
            ),
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(parent=file_share_mirror_manager)
            ),
        )

        # Define the container group.
        self.container_group_name = f"{stack_name}-container-group-mirror-manager"
        self.container_group = containerinstance.ContainerGroup(
            f"{self._name}_container_group",
            container_group_name=self.container_group_name,
            containers=[
                containerinstance.ContainerArgs(
                    image="xr09/python-requests:3.11",
                    name="mirrormanager",
                    command=["python", "/etc/scripts/mirrors.py"],
                    environment_variables=[
                        # TODO(cgavidia): Replace later with proper values. And passwords from Secrets.
                        containerinstance.EnvironmentVariableArgs(
                            name="MIRROR_SERVER_URL",
                            value="http://gitea.ronsocosandbox.cvdnetdev.develop.turingsafehaven.ac.uk",
                        ),
                        containerinstance.EnvironmentVariableArgs(
                            name="MIRROR_SERVER_USERNAME", value="carlos.gavidia"
                        ),
                        containerinstance.EnvironmentVariableArgs(
                            name="MIRROR_SERVER_PASSWORD", value="TBA"
                        ),
                        containerinstance.EnvironmentVariableArgs(
                            name="WORKSPACE_SERVER_URL",
                            value="http://gitea.ronsocosandbox.cvdnetdev.develop.turingsafehaven.ac.uk",
                        ),
                        containerinstance.EnvironmentVariableArgs(
                            name="WORKSPACE_SERVER_USERNAME", value="carlos.gavidia"
                        ),
                        containerinstance.EnvironmentVariableArgs(
                            name="WORKSPACE_SERVER_PASSWORD", value="TBA"
                        ),
                        containerinstance.EnvironmentVariableArgs(
                            name="REPOSITORY_DATA",
                            value='{"repositories": [{"repository_name":"data-safe-haven","repository_url":"https://github.com/cptanalatriste/data-safe-haven","repository_auth_token":"TBA"}]}',
                        ),
                    ],
                    ports=[
                        containerinstance.ContainerPortArgs(
                            port=80,
                            protocol=containerinstance.ContainerGroupNetworkProtocol.TCP,
                        ),
                    ],
                    resources=containerinstance.ResourceRequirementsArgs(
                        requests=containerinstance.ResourceRequestsArgs(
                            cpu=0.5,
                            memory_in_gb=0.5,
                        ),
                    ),
                    volume_mounts=[
                        containerinstance.VolumeMountArgs(
                            mount_path="/etc/scripts",
                            name="mirror-manager-etc-scripts",
                            read_only=True,
                        ),
                    ],
                )
            ],
            diagnostics=containerinstance.ContainerGroupDiagnosticsArgs(
                log_analytics=containerinstance.LogAnalyticsArgs(
                    workspace_id=props.log_analytics_workspace.workspace_id, # type: ignore
                    workspace_key=props.log_analytics_workspace.workspace_key, # type: ignore
                ),
            ),
            dns_config=containerinstance.DnsConfigurationArgs(
                name_servers=[props.dns_server_ip],
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
            restart_policy=containerinstance.ContainerGroupRestartPolicy.ON_FAILURE,
            sku=containerinstance.ContainerGroupSku.STANDARD,
            subnet_ids=[
                containerinstance.ContainerGroupSubnetIdArgs(
                    id=props.mirror_manager_subnet_id
                )
            ],
            volumes=[
                containerinstance.VolumeArgs(
                    azure_file=containerinstance.AzureFileVolumeArgs(
                        share_name=file_share_mirror_manager.name,
                        storage_account_key=props.storage_account_key,
                        storage_account_name=props.storage_account_name,
                    ),
                    name="mirror-manager-etc-scripts",
                )],
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    delete_before_replace=True,
                    depends_on=[
                        file_share_mirror_manager_python_script
                    ],
                    replace_on_changes=["containers"],
                ),
            ),
            tags=child_tags,

        )
