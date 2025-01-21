from data_safe_haven.allowlist import Allowlist
from data_safe_haven.external import AzureSdk
from data_safe_haven.provisioning.sre_provisioning_manager import SREProjectManager
from data_safe_haven.types import AllowlistRepository


class TestAllowlist:
    def test_from_remote(
        self, mocker, context, sre_config, pulumi_config_no_key
    ) -> None:

        mocker.patch.object(
            SREProjectManager,
            "output",
            return_value={"storage_account_data_configuration_name": "test"},
        )
        mocker.patch.object(
            AzureSdk,
            "download_share_file",
            return_value="tidyverse\ndplyr\nnumpy",
        )
        result = Allowlist.from_remote(
            context,
            pulumi_config=pulumi_config_no_key,
            repository=AllowlistRepository.CRAN,
            sre_config=sre_config,
        )
        assert "dplyr" in result

    def test_remote_exists(
        self, mocker, context, sre_config, pulumi_config_no_key
    ) -> None:
        mocker.patch.object(
            AzureSdk,
            "file_share_exists",
            return_value=True,
        )
        mocker.patch.object(
            SREProjectManager,
            "output",
            return_value={"storage_account_data_configuration_name": "test"},
        )

        exists = Allowlist.remote_exists(
            context,
            pulumi_config=pulumi_config_no_key,
            repository=AllowlistRepository.CRAN,
            sre_config=sre_config,
        )
        assert exists
