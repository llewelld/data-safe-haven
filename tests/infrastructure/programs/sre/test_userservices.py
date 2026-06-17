from typing import Any
from unittest.mock import patch

import pulumi
import pulumi.runtime
import pytest
from pulumi_azure_native import resources
from pytest import fixture

from data_safe_haven.config.config_sections import (
    ConfigSubsectionGiteaMirror,
)
from data_safe_haven.infrastructure.common import (
    DockerHubCredentials,
)
from data_safe_haven.infrastructure.programs.sre.dns_server import (
    SREDnsServerComponent,
)
from data_safe_haven.infrastructure.programs.sre.monitoring_elements import (
    SREMonitoringElementsComponent,
)
from data_safe_haven.infrastructure.programs.sre.networking import (
    SRENetworkingComponent,
)
from data_safe_haven.infrastructure.programs.sre.user_services import (
    SREUserServicesComponent,
    SREUserServicesProps,
)
from data_safe_haven.types import (
    DatabaseSystem,
    SoftwarePackageCategory,
)


class DataSafeHavenMocks(pulumi.runtime.Mocks):
    """Configuration for Pulumi mocks"""

    def new_resource(
        self, args: pulumi.runtime.MockResourceArgs
    ) -> tuple[str | None, dict[Any, Any]]:
        state = dict(args.inputs)

        if args.typ == "azure-native:dns:Zone":
            # Ensure a value is available for the nameservers
            # Otherwise these come through as None and the tests fail
            state["nameServers"] = [
                "ns1.example.com",
            ]
        elif args.typ == "azure-native:network:VirtualNetwork":
            # Ensure a value is set for the VirtualNetwork name
            # Otherwise this comes through as None and the tests fail
            state["name"] = state["virtualNetworkName"]

        resources = (args.name + "_id", state)
        return resources

    def call(
        self, args: pulumi.runtime.MockCallArgs
    ) -> tuple[dict[Any, Any], list[tuple[str, str]] | None]:
        if args.token == "azure-native:network:getSubnet":  # noqa: S105
            # Ensure we return a validly formed subnet
            # Otherwise this comes through as None and the tests fail
            return (
                {
                    "id": "/subscriptions/test/subnets/subnet1",
                    "name": "subnet1",
                    "addressPrefix": "10.0.0.0/24",
                },
                [],
            )
        return ({}, [])


## Avoids a delayed return value causing the tests to fail
@fixture(autouse=True)
def patch_ips() -> pulumi.Output[list[str]]:
    with patch(
        "data_safe_haven.infrastructure.components.composite.postgresql_database.get_ip_addresses_from_private_endpoint"
    ) as mock:
        mock.return_value = pulumi.Output.from_input(["10.0.0.0"])
        yield mock


# Ensure the dns_zone is set. This is equivalent to setting:
# os.environ["PULUMI_CONFIG"] = '{"project:dnsZone":"example.com"}'
@fixture(autouse=True)
def patch_config() -> pulumi.Output[str]:
    with patch(
        "pulumi.Config.require", side_effect=pulumi_config_require_side_effect
    ) as mock:
        yield mock


def pulumi_config_require_side_effect(key: str) -> str:
    values = {
        "dnsZone": "example.com",
    }
    return values[key]


# Set the Pulumi mocks for testing
mocks = DataSafeHavenMocks()
pulumi.runtime.set_mocks(
    mocks,
    preview=False,
)


# Fixture for the User Services Component properties for testing
@fixture
def user_services_props(
    dns: SREDnsServerComponent,
    dockerhub_credentials: DockerHubCredentials,
    ldap_username_attribute: str,
    ldap_user_filter: str,
    ldap_user_search_base: str,
    location: str,
    monitoring_elements: SREMonitoringElementsComponent,
    resource_group: resources.ResourceGroup,
    sre_fqdn: str,
    networking: SRENetworkingComponent,
    repository_data: ConfigSubsectionGiteaMirror,
) -> SREUserServicesProps:
    return SREUserServicesProps(
        database_service_admin_password="db_password",
        databases=[DatabaseSystem.POSTGRESQL],
        dns_server_ip=dns.ip_address,
        dockerhub_credentials=dockerhub_credentials,
        ldap_server_hostname="identity.none",
        ldap_server_port=9999,
        ldap_username_attribute=ldap_username_attribute,
        ldap_user_filter=ldap_user_filter,
        ldap_user_search_base=ldap_user_search_base,
        location=location,
        log_analytics_workspace=monitoring_elements.workspace_analytics,
        nexus_admin_password="nexus_password",
        resource_group_name=resource_group.name,
        software_packages=SoftwarePackageCategory.NONE,
        sre_fqdn=sre_fqdn,
        nexus_persistent_quota_gb=10,
        repository_data=repository_data,
        storage_account_key="storage_key",
        storage_account_name="storage_account",
        software_repositories_database_password="repo_password",
        subnet_containers=networking.subnet_identity_containers,
        subnet_containers_support=networking.subnet_user_services_containers_support,
        subnet_gitea_mirrors=networking.subnet_user_services_gitea_mirror,
        subnet_databases=networking.subnet_user_services_databases,
        subnet_software_repositories=networking.subnet_user_services_software_repositories,
        subnet_software_repositories_support=networking.subnet_user_services_software_repositories_support,
        db_server_shared_password="shared-db-password",
        db_server_shared_username="shared_db-username",
    )


# Fixture for the User Services Component for testing
@pytest.fixture
def user_services_component(
    user_services_props: SREUserServicesProps,
    stack_name: str,
    tags: dict[str, str],
) -> SREUserServicesComponent:
    return SREUserServicesComponent(
        name="userservices-name",
        stack_name=stack_name,
        props=user_services_props,
        tags=tags,
    )


# The test suite
class TestSREUserServicesProps:
    @pulumi.runtime.test  # type: ignore
    def test_user_service_props_creation(
        self, user_services_props: SREUserServicesProps
    ) -> None:
        """Basic test to ensure properties are being created correctly"""
        assert isinstance(user_services_props, SREUserServicesProps)

    @pulumi.runtime.test  # type: ignore
    def test_user_service_creation(
        self, user_services_component: SREUserServicesComponent
    ) -> None:
        """Basic test to ensure components are being created correctly"""
        assert isinstance(user_services_component, SREUserServicesComponent)

    @pulumi.runtime.test  # type: ignore
    def test_shared_db_usernames(
        self, user_services_component: SREUserServicesComponent
    ) -> None:
        """Check that the username for the shared database is shared correctly across components"""

        def check(inputs: list[Any]) -> None:
            usernames = {inputs[0]}
            for component in inputs[1:]:
                usernames.add(
                    next(
                        env["value"]
                        for env in component[1]["environment_variables"]
                        if env["name"] == "GITEA__database__USER"
                    )
                )

            assert len(set(usernames)) == 1

        pulumi.Output.from_input(
            [
                user_services_component.db_server_shared.db_server.administrator_login,
                user_services_component.gitea_server.container_group.containers,
                user_services_component.mirror_monitor.container_group.containers,
            ]
        ).apply(check)

    @pulumi.runtime.test  # type: ignore
    def test_shared_db_passwords(
        self,
        user_services_component: SREUserServicesProps,
        user_services_props: SREUserServicesProps,
    ) -> None:
        """Check that the password for the shared database is shared correctly across components"""

        def check(inputs: list[Any]) -> None:
            usernames = {inputs[0]}
            for component in inputs[1:]:
                usernames.add(
                    next(
                        env["secure_value"]
                        for env in component[1]["environment_variables"]
                        if env["name"] == "GITEA__database__PASSWD"
                    )
                )

            assert len(set(usernames)) == 1

        pulumi.Output.from_input(
            [
                user_services_props.db_server_shared_password,
                user_services_component.gitea_server.container_group.containers,  # type: ignore[attr-defined]
                user_services_component.mirror_monitor.container_group.containers,  # type: ignore[attr-defined]
            ]
        ).apply(check)

    @pulumi.runtime.test  # type: ignore
    def test_shared_db_subnet_gitea(
        self, user_services_component: SREUserServicesComponent
    ) -> Any:
        """Check that the Gitea service is in the same subnet as the shared database"""

        def check(subnets: dict[Any, Any]) -> None:
            assert subnets["db_subnet"] in [
                subnet["id"] for subnet in subnets["component_subnets"]
            ]

        return pulumi.Output.from_input(
            {
                "db_subnet": user_services_component.db_server_shared.private_endpoint.subnet.id,
                "component_subnets": user_services_component.gitea_server.container_group.subnet_ids,
            }
        ).apply(check)

    @pulumi.runtime.test  # type: ignore
    def test_shared_db_subnet_hedgedoc(
        self, user_services_component: SREUserServicesComponent
    ) -> Any:
        """Check that the Hedgedock service is in the same subnet as the shared database"""

        def check(subnets: dict[Any, Any]) -> None:
            assert subnets["db_subnet"] in [
                subnet["id"] for subnet in subnets["component_subnets"]
            ]

        return pulumi.Output.from_input(
            {
                "db_subnet": user_services_component.db_server_shared.private_endpoint.subnet.id,
                "component_subnets": user_services_component.hedgedoc_server.container_group.subnet_ids,
            }
        ).apply(check)

    @pulumi.runtime.test  # type: ignore
    def test_shared_db_subnet_gitea_mirror(
        self, user_services_component: SREUserServicesComponent
    ) -> Any:
        """Check that the Gitea Mirror service is in the same subnet as the shared database"""

        def check(subnets: dict[Any, Any]) -> None:
            assert subnets["db_subnet"] in [
                subnet["id"] for subnet in subnets["component_subnets"]
            ]

        return pulumi.Output.from_input(
            {
                "db_subnet": user_services_component.db_server_shared.private_endpoint.subnet.id,
                "component_subnets": user_services_component.mirror_monitor.container_group.subnet_ids,
            }
        ).apply(check)
