from data_safe_haven.allowlist import Allowlist
from data_safe_haven.external import AzureSdk
from data_safe_haven.provisioning.sre_provisioning_manager import SREProjectManager
from data_safe_haven.types import AllowlistRepository


class TestAllowlist:
    def test_from_remote(
        self,
        mocker,
        context,
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
            sre_resource_group="test-rg",
            repository=AllowlistRepository.CRAN,
            storage_account_name="test",
        )
        assert "dplyr" in result

    def test_remote_exists(
        self,
        mocker,
        context,
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
            sre_resource_group="test-rg",
            repository=AllowlistRepository.CRAN,
            storage_account_name="test",
        )

        assert isinstance(exists, bool)
        assert exists

    def test_remote_diff(
        self,
        mocker,
        context,
    ) -> None:
        mocker.patch.object(
            SREProjectManager,
            "output",
            return_value={"storage_account_data_configuration_name": "test"},
        )
        mocker.patch.object(
            AzureSdk, "download_share_file", return_value="tidyverse\ndplyr\nnumpy"
        )
        local_allowlist = "tidyverse\ndplyr\nnumpy\npandas"
        diff = Allowlist.remote_diff(
            context=context,
            sre_resource_group="test-rg",
            repository=AllowlistRepository.CRAN,
            storage_account_name="test",
            allowlist=local_allowlist,
        )

        assert isinstance(diff, list)
        assert "+pandas" in diff

    def test_remote_diff_no_change(
        self,
        mocker,
        context,
    ) -> None:
        mocker.patch.object(
            SREProjectManager,
            "output",
            return_value={"storage_account_data_configuration_name": "test"},
        )
        mocker.patch.object(
            AzureSdk, "download_share_file", return_value="tidyverse\ndplyr\nnumpy"
        )
        local_allowlist = "tidyverse\ndplyr\nnumpy"
        diff = Allowlist.remote_diff(
            context=context,
            sre_resource_group="test-rg",
            repository=AllowlistRepository.CRAN,
            storage_account_name="test",
            allowlist=local_allowlist,
        )

        assert isinstance(diff, list)
        assert not diff
