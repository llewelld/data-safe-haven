from collections.abc import Mapping

import chevron
from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_azure_native import network

from data_safe_haven.functions import b64encode, replace_separators
from data_safe_haven.infrastructure.common import (
    DockerHubCredentials,
    get_available_ips_from_subnet,
    get_name_from_subnet,
    get_name_from_vnet,
)
from data_safe_haven.infrastructure.components import LinuxVMComponentProps, VMComponent
from data_safe_haven.logging import get_logger
from data_safe_haven.resources import resources_path


class SREDnsServerVMProps:
    """Properties for the SREDnsServerVM component"""

    def __init__(
        self,
        adguardhome_yaml_content: Input[str],
        admin_password: Input[str],
        dockerhub_credentials: DockerHubCredentials,
        entrypoint_sh_content: str,
        location: Input[str],
        resource_group_name: Input[str],
        subnet_dns: Input[network.GetSubnetResult],
        virtual_network: Input[network.VirtualNetwork],
        vm_size: Input[str],
    ):
        self.adguardhome_yaml_content_encoded = Output.from_input(
            adguardhome_yaml_content
        ).apply(b64encode)
        self.admin_password = Output.secret(admin_password)
        self.admin_username = "dshadmin"
        self.dockerhub_username = dockerhub_credentials.username
        self.dockerhub_access_token = dockerhub_credentials.access_token
        self.entrypoint_sh_content_encoded = b64encode(entrypoint_sh_content)
        self.location = location
        self.resource_group_name = resource_group_name

        self.subnet_dns_server_name = Output.from_input(subnet_dns).apply(
            get_name_from_subnet
        )
        self.subnet_ip_addresses = Output.from_input(subnet_dns).apply(
            lambda subnet: get_available_ips_from_subnet(subnet)
        )

        self.virtual_network_name: Output[str] = Output.from_input(
            virtual_network
        ).apply(get_name_from_vnet)
        self.vm_size = vm_size

        # TODO(cgavidia): Only for testing
        # import pulumi

        # self.subnet_dns_server_name.apply(lambda value: pulumi.error(value))
        # self.subnet_ip_addresses.apply(lambda value: pulumi.error(value))
        # self.virtual_network_name.apply(lambda value: pulumi.error(value))


class SREDnsServerVMComponent(ComponentResource):
    """Deploy a VM-based DNS Server with Pulumi"""

    def __init__(
        self,
        name: str,
        stack_name: str,
        props: SREDnsServerVMProps,
        opts: ResourceOptions | None = None,
        tags: Input[Mapping[str, Input[str]]] | None = None,
    ) -> None:
        super().__init__("dsh:sre:SREDnsServerVMComponent", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))
        child_tags = {"component": "workspaces"} | (tags if tags else {})

        # Load cloud-init file
        cloud_init = Output.all(
            entrypoint_sh_content_encoded=props.entrypoint_sh_content_encoded,
            adguardhome_yaml_content_encoded=props.adguardhome_yaml_content_encoded,
            dockerhub_username=props.dockerhub_username,
            dockerhub_access_token=props.dockerhub_access_token,
        ).apply(lambda kwargs: self.template_cloudinit(**kwargs))

        container_host_vm = VMComponent(
            name=replace_separators(f"{self._name}_vm_workspace_", "_"),
            props=LinuxVMComponentProps(
                admin_password=props.admin_password,
                admin_username=props.admin_username,
                b64cloudinit=cloud_init.apply(b64encode),
                ip_address_private=props.subnet_ip_addresses[0],
                location=props.location,
                resource_group_name=props.resource_group_name,
                # secondary_private_ip_address=props.subnet_ip_addresses[1],
                subnet_name=props.subnet_dns_server_name,
                virtual_network_name=props.virtual_network_name,
                virtual_network_resource_group_name=props.resource_group_name,
                vm_name=Output.concat(stack_name, "-vm-dns-server").apply(
                    lambda s: replace_separators(s, "-")
                ),
                vm_size=props.vm_size,
            ),
            opts=child_opts,
            tags=child_tags,
        )

        # Get details of the deployed VM and register exports.
        self.exports = {
            "ip_address": container_host_vm.ip_address_private,
            "name": container_host_vm.vm_name,
            "sku": container_host_vm.vm_size,
        }

    @staticmethod
    def template_cloudinit(**kwargs: str) -> str:
        logger = get_logger()

        with open(
            resources_path / "dns_server" / "dns_server_vm.cloud_init.mustache.yaml",
            encoding="utf-8",
        ) as f_cloudinit:
            cloudinit = chevron.render(f_cloudinit, kwargs)
            logger.debug(
                f"Generated cloud-init config: {cloudinit.replace('\n', r'\n')}"
            )

            return cloudinit
