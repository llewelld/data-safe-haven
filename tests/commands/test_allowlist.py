from pytest import fixture, mark

from data_safe_haven.allowlist import Allowlist
from data_safe_haven.commands.allowlist import allowlist_command_group


@fixture
def test_allowlist():
    allowlist = """tidyverse\ndplyr\nnumpy"""
    return allowlist


class TestShowAllowlist:
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
        mocker.patch.object(Allowlist, "from_remote", return_value=test_allowlist)
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
