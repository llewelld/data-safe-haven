from pytest import fixture, mark

from data_safe_haven.allowlist import Allowlist
from data_safe_haven.commands.allowlist import allowlist_command_group
from data_safe_haven.external import AzureSdk
from data_safe_haven.infrastructure import SREProjectManager


@fixture
def test_allowlist():
    return "tidyverse\ndplyr\nnumpy"


@fixture
def allowlist_file(test_allowlist, tmp_path):
    allowlist_file_path = tmp_path / "allowlist.txt"
    with open(allowlist_file_path, "w") as f:
        f.write(test_allowlist)
    return allowlist_file_path


class TestShowAllowlist:
    def test_show(
        self,
        mocker,
        runner,
        mock_azuresdk_get_credential,  # noqa: ARG002
        mock_azuresdk_get_subscription,  # noqa: ARG002
        mock_sre_config_from_remote,  # noqa: ARG002
        mock_pulumi_config_no_key_from_remote,  # noqa: ARG002,
        test_allowlist,
    ) -> None:
        sre_name = "sandbox"
        repository = "cran"
        mocker.patch.object(Allowlist, "from_remote", return_value=test_allowlist)
        mocker.patch.object(
            SREProjectManager,
            "output",
            return_value={"storage_account_data_configuration_name": "test"},
        )
        result = runner.invoke(
            allowlist_command_group,
            ["show", sre_name, repository],
        )
        assert result.exit_code == 0
        assert "tidyverse\ndplyr\nnumpy" in result.output


class TestTemplateAllowlist:
    @mark.parametrize(
        "repository",
        [
            "cran",
            "pypi",
        ],
    )
    def test_template(self, runner, repository) -> None:

        result = runner.invoke(
            allowlist_command_group,
            ["template", repository],
        )
        assert result.exit_code == 0
        if repository == "cran":
            assert "DBI\nMASS" in result.output
        elif repository == "pypi":
            assert "numpy\npackaging" in result.output


class TestUploadAllowlist:
    @mark.parametrize(
        "repository",
        [
            "cran",
            "pypi",
        ],
    )
    def test_upload_no_remote(
        self,
        mocker,
        runner,
        repository,
        allowlist_file,
        mock_azuresdk_get_subscription,  # noqa: ARG002
        mock_pulumi_config_no_key_from_remote,  # noqa: ARG002
        mock_sre_config_from_remote,  # noqa: ARG002
        mock_azuresdk_get_credential,  # noqa: ARG002
    ) -> None:
        sre_name = "sandbox"
        mocker.patch.object(
            SREProjectManager,
            "output",
            return_value={"storage_account_data_configuration_name": "test"},
        )
        mocker.patch.object(AzureSdk, "upload_file_share", return_value=None)
        mocker.patch.object(Allowlist, "remote_exists", return_value=False)

        result = runner.invoke(
            allowlist_command_group,
            ["upload", sre_name, str(allowlist_file), repository],
        )
        assert result.exit_code == 0

    @mark.parametrize(
        "repository",
        [
            "cran",
            "pypi",
        ],
    )
    def test_upload_remote_exists_no_diff(
        self,
        mocker,
        runner,
        repository,
        allowlist_file,
        mock_azuresdk_get_subscription,  # noqa: ARG002
        mock_pulumi_config_no_key_from_remote,  # noqa: ARG002
        mock_sre_config_from_remote,  # noqa: ARG002
        mock_azuresdk_get_credential,  # noqa: ARG002
    ) -> None:
        sre_name = "sandbox"
        mocker.patch.object(
            SREProjectManager,
            "output",
            return_value={"storage_account_data_configuration_name": "test"},
        )
        mocker.patch.object(AzureSdk, "upload_file_share", return_value=None)
        mocker.patch.object(Allowlist, "remote_exists", return_value=True)
        mocker.patch.object(Allowlist, "remote_diff", return_value=[])

        result = runner.invoke(
            allowlist_command_group,
            ["upload", sre_name, str(allowlist_file), repository],
        )
        assert result.exit_code == 0
        assert "No changes, won't upload allowlist." in result.output

    def test_upload_remote_exists_with_diff(
        self,
        mocker,
        runner,
        allowlist_file,
        mock_azuresdk_get_subscription,  # noqa: ARG002
        mock_pulumi_config_no_key_from_remote,  # noqa: ARG002
        mock_sre_config_from_remote,  # noqa: ARG002
        mock_azuresdk_get_credential,  # noqa: ARG002
    ) -> None:
        sre_name = "sandbox"
        repository = "cran"
        mocker.patch.object(
            SREProjectManager,
            "output",
            return_value={"storage_account_data_configuration_name": "test"},
        )
        mocker.patch.object(AzureSdk, "upload_file_share", return_value=None)
        mocker.patch.object(Allowlist, "remote_exists", return_value=True)
        mocker.patch.object(
            Allowlist, "remote_diff", return_value=["-numpy", "+pandas"]
        )

        result = runner.invoke(
            allowlist_command_group,
            ["upload", sre_name, str(allowlist_file), repository],
            input="y\n",
        )

        assert "-numpy" in result.output
        assert result.exit_code == 0
        assert "An allowlist already exists" in result.output
        assert "Uploading allowlist for CRAN to sandbox" in result.output
