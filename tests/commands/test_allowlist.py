from pytest import fixture

from data_safe_haven.allowlist import SREAllowlist
from data_safe_haven.commands.allowlist import allowlist_command_group


@fixture
def test_allowlist():
    allowlist = """tidyverse\ndplyr\nnumpy"""
    return allowlist


class TestAllowlist:
    def test_show(
        self,
        mocker,
        runner,
        mock_azuresdk_get_credential,  # noqa: ARG002
        mock_sre_config_from_remote,  # noqa: ARG002
        mock_pulumi_config_no_key_from_remote,  # noqa: ARG002
        test_allowlist,
    ) -> None:
        sre_name = "sandbox"
        repository = "cran"
        mocker.patch.object(SREAllowlist, "from_remote", return_value=test_allowlist)
        result = runner.invoke(
            allowlist_command_group,
            ["show", sre_name, repository],
        )
        assert result.exit_code == 0
        assert "tidyverse\ndplyr\nnumpy" in result.output
