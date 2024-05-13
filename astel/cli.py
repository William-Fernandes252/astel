"""Console script for astel."""

import asyncio
import sys
from typing import Callable, List, Union

import click

from astel.crawler import Crawler
from astel.options import CrawlerOptions


def cli_for(
    crawler_factory: Callable[[List[str], CrawlerOptions], Crawler],
) -> Callable[..., int]:
    """Return a CLI function for the given crawler factory.

    Args:
        crawler_factory (Callable[[List[str], CrawlerOptions], Crawler]): A factory
        function that returns a Crawler instance.

    Returns:
        Callable[..., int]: A CLI function.
    """

    @click.command("astel")
    @click.argument("urls", required=True, type=str, nargs=-1)
    @click.option(
        "--workers",
        "-w",
        type=int,
        default=5,
        show_default=True,
        help="Number of workers to use.",
    )
    @click.option(
        "--limit",
        "-l",
        type=int,
        default=20,
        show_default=True,
        help="Maximum number of URLs to crawl.",
    )
    @click.option(
        "--agent",
        "-u",
        type=str,
        default="astel",
        show_default=True,
        help="User agent to use for the requests.",
    )
    def main(*urls: str, **kwargs: Union[int, str]) -> int:
        """Console script for astel."""
        crawler = crawler_factory(
            list(urls),
            {
                "workers": int(kwargs["workers"]),
                "limit": int(kwargs["limit"]),
                "user_agent": str(kwargs["agent"]),
            },
        )
        asyncio.run(crawler.run())
        click.secho(f"Visited {len(crawler.urls_seen)} URLs:", fg="green")
        for url in crawler.urls_seen:
            click.echo(url)
        return 0

    return main


main = cli_for(Crawler)


if __name__ == "__main__":
    sys.exit(main())
