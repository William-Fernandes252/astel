from typing import cast

from click import Command
from click.testing import CliRunner
from pytest_mock import MockerFixture


class DescribeCli:
    def it_should_return_a_cli_function(self, mocker: MockerFixture):
        from naja.cli import cli_for

        assert callable(cli_for(mocker.MagicMock()))

    def it_should_run_the_crawler(self, mocker: MockerFixture):
        from naja.cli import cli_for

        crawler_mock = mocker.MagicMock(urls_seen=[], run=mocker.AsyncMock())

        runner = CliRunner()
        result = runner.invoke(
            cast(
                Command,
                cli_for(mocker.MagicMock(return_value=crawler_mock)),
            ),
            ["https://example.com"],
        )

        assert result.exit_code == 0
        assert result.output == "Visited 0 URLs:\n"
