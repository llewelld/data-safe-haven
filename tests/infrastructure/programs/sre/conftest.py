import asyncio
from typing import Any

import pulumi
import pulumi.runtime
from pulumi_azure_native import managedidentity, network, resources
from pytest import fixture

from data_safe_haven.config.config_sections import (
    ConfigSubsectionGiteaMirror,
)
from data_safe_haven.infrastructure.common import (
    DockerHubCredentials,
    SREIpRanges,
)
from data_safe_haven.infrastructure.programs.sre.dns_server import (
    SREDnsServerComponent,
    SREDnsServerProps,
)
from data_safe_haven.infrastructure.programs.sre.monitoring_elements import (
    SREMonitoringElementsComponent,
    SREMonitoringElementsProps,
)
from data_safe_haven.infrastructure.programs.sre.networking import (
    SRENetworkingComponent,
    SRENetworkingProps,
)


class DataSafeHavenMocks(pulumi.runtime.Mocks):
    """Configuration for Pulumi mocks"""

    def __init__(self) -> None:
        # Avoid "DeprecationWarning: There is no current event loop"
        # See https://stackoverflow.com/a/73884759
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    def new_resource(
        self, args: pulumi.runtime.MockResourceArgs
    ) -> tuple[str | None, dict[Any, Any]]:
        resources = (args.name + "_id", args.inputs)
        return resources

    def call(
        self, _: pulumi.runtime.MockCallArgs
    ) -> tuple[dict[Any, Any], list[tuple[str, str]] | None]:
        return ({}, [])


pulumi.runtime.set_mocks(
    DataSafeHavenMocks(),
    preview=False,
)


#
# Constants
#
@fixture
def location() -> str:
    return "uksouth"


@fixture
def resource_group_name() -> str:
    return "rg-example"


@fixture
def resource_group(location: str, resource_group_name: str) -> resources.ResourceGroup:
    return resources.ResourceGroup(
        "resource_group",
        location=location,
        resource_group_name=resource_group_name,
    )


@fixture
def sre_fqdn() -> str:
    return "sre.example.com"


@fixture
def sre_index() -> int:
    return 1


@fixture
def stack_name() -> str:
    return "stack-example"


@fixture
def tags() -> dict[str, str]:
    return {"key": "value"}


@fixture
def shm_fqdn() -> str:
    return "shm.example.com"


@fixture
def ldap_root_dn(shm_fqdn: str) -> str:
    return f"DC={shm_fqdn.replace('.', ',DC=')}"


@fixture
def ldap_group_search_base(ldap_root_dn: str) -> str:
    return f"OU=groups,{ldap_root_dn}"


@fixture
def ldap_username_attribute() -> str:
    return "uid"


@fixture
def ldap_user_search_base(ldap_root_dn: str) -> str:
    return f"OU=users,{ldap_root_dn}"


@fixture
def ldap_server_hostname() -> str:
    return "ldap_server.example.com}"


@fixture
def timezone() -> str:
    return "UTC"


#
# Pulumi resources
#
@fixture
def identity_key_vault_reader(
    location: str, resource_group_name: str, stack_name: str
) -> managedidentity.UserAssignedIdentity:
    return managedidentity.UserAssignedIdentity(
        "identity_key_vault_reader",
        location=location,
        resource_group_name=resource_group_name,
        resource_name_=f"{stack_name}-id-key-vault-reader",
    )


@fixture
def subnet_application_gateway() -> network.GetSubnetResult:
    return network.GetSubnetResult(
        address_prefix=SREIpRanges.application_gateway.prefix,
        id="subnet_application_gateway_id",
    )


@fixture
def subnet_guacamole_containers() -> network.GetSubnetResult:
    return network.GetSubnetResult(
        address_prefix=SREIpRanges.guacamole_containers.prefix,
        id="subnet_guacamole_containers_id",
    )


@fixture
def subnet_apt_proxy_server() -> network.GetSubnetResult:
    return network.GetSubnetResult(
        address_prefix=SREIpRanges.apt_proxy_server.prefix,
        id="subnet_apt_proxy_server_id",
    )


@fixture
def subnet_clamav_mirror() -> network.GetSubnetResult:
    return network.GetSubnetResult(
        address_prefix=SREIpRanges.clamav_mirror.prefix,
        id="subnet_clamav_mirror_id",
    )


@fixture
def subnet_firewall() -> network.GetSubnetResult:
    return network.GetSubnetResult(
        address_prefix=SREIpRanges.firewall.prefix,
        id="subnet_firewall_id",
    )


@fixture
def subnet_firewall_management() -> network.GetSubnetResult:
    return network.GetSubnetResult(
        address_prefix=SREIpRanges.firewall_management.prefix,
        id="subnet_firewall_management_id",
    )


@fixture
def subnet_identity_containers() -> network.GetSubnetResult:
    return network.GetSubnetResult(
        address_prefix=SREIpRanges.identity_containers.prefix,
        id="subnet_identity_containers_id",
    )


@fixture
def subnet_user_services_software_repositories() -> network.GetSubnetResult:
    return network.GetSubnetResult(
        address_prefix=SREIpRanges.user_services_software_repositories.prefix,
        id="subnet_user_services_software_repositories_id",
    )


@fixture
def subnet_user_services_gitea_mirror() -> network.GetSubnetResult:
    return network.GetSubnetResult(
        address_prefix=SREIpRanges.user_services_gitea_mirror.prefix,
        id="subnet_user_services_gitea_mirror_id",
    )


@fixture
def subnet_user_services_containers() -> network.GetSubnetResult:
    return network.GetSubnetResult(
        address_prefix=SREIpRanges.user_services_containers.prefix,
        id="subnet_user_services_containers_id",
    )


@fixture
def subnet_workspaces() -> network.GetSubnetResult:
    return network.GetSubnetResult(
        address_prefix=SREIpRanges.workspaces.prefix,
        id="subnet_workspaces_id",
    )


@fixture
def subnet_monitoring() -> network.GetSubnetResult:
    return network.GetSubnetResult(
        address_prefix=SREIpRanges.monitoring.prefix,
        id="subnet_monitoring_id",
    )


@fixture
def subnet_dns_sidecar() -> network.GetSubnetResult:
    return network.GetSubnetResult(
        address_prefix=SREIpRanges.dns_sidecar.prefix,
        id="subnet_dns_sidecar_id",
    )


@fixture
def dockerhub_credentials() -> DockerHubCredentials:
    return DockerHubCredentials(
        access_token="docker_token",
        server="docker_server",
        username="docker_username",
    )


@fixture
def ldap_user_filter(ldap_group_search_base: str) -> str:
    ldap_group_name_prefix = "Data Safe Haven SRE unit test"
    ldap_group_names = {
        "admin_group_name": f"{ldap_group_name_prefix} Administrators",
        "privileged_user_group_name": f"{ldap_group_name_prefix} Privileged Users",
        "user_group_name": f"{ldap_group_name_prefix} Users",
    }
    return "".join(
        [
            "(&",
            "(objectClass=posixAccount)",
            "(|",
            *(
                f"(memberOf=CN={group_name},{ldap_group_search_base})"
                for group_name in ldap_group_names.values()
            ),
            ")",
            ")",
        ]
    )


@fixture
def monitoring_elements(
    stack_name: str,
    location: str,
    resource_group: resources.ResourceGroup,
    tags: dict[str, str],
    timezone: str,
) -> SREMonitoringElementsComponent:
    return SREMonitoringElementsComponent(
        "sre_monitoring_elements",
        stack_name,
        SREMonitoringElementsProps(
            location=location,
            resource_group_name=resource_group.name,
            timezone=timezone,
        ),
        tags=tags,
    )


@fixture
def dns(
    stack_name: str,
    monitoring_elements: SREMonitoringElementsComponent,
    dockerhub_credentials: DockerHubCredentials,
    location: str,
    resource_group: resources.ResourceGroup,
    shm_fqdn: str,
    tags: dict[str, str],
    timezone: str,
) -> SREDnsServerComponent:
    return SREDnsServerComponent(
        "sre_dns_server",
        stack_name,
        SREDnsServerProps(
            allow_workspace_internet=False,
            data_collection_endpoint_id=monitoring_elements.data_collection_endpoint.id,
            data_collection_rule_id=monitoring_elements.data_collection_rule_vms.id,
            dockerhub_credentials=dockerhub_credentials,
            location=location,
            resource_group_name=resource_group.name,
            maintenance_configuration_id=monitoring_elements.maintenance_configuration.id,
            shm_fqdn=shm_fqdn,
            timezone=timezone,
        ),
        tags=tags,
    )


@fixture
def networking(
    stack_name: str,
    dns: SREDnsServerComponent,
    location: str,
    resource_group: resources.ResourceGroup,
    shm_fqdn: str,
    tags: dict[str, str],
) -> SRENetworkingComponent:
    return SRENetworkingComponent(
        "sre_networking",
        stack_name,
        SRENetworkingProps(
            dns_private_zones=dns.private_zones,
            dns_server_ip=dns.ip_address,
            dns_virtual_network=dns.virtual_network,
            location=location,
            resource_group_name=resource_group.name,
            shm_fqdn=shm_fqdn,
            shm_location=location,
            shm_resource_group_name=resource_group.name,
            shm_subscription_id="abcd-0123-abcd-0123",
            shm_zone_name=shm_fqdn,
            sre_name="sre-name",
            use_gitea_mirror=True,
            use_software_repositories=True,
            user_public_ip_ranges=["10.0.0.0/24"],
        ),
        tags=tags,
    )


@fixture
def repository_data() -> ConfigSubsectionGiteaMirror:
    return ConfigSubsectionGiteaMirror(
        repositories=[],
    )
