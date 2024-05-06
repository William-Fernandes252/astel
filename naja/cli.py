"""Console script for naja."""

import sys

import click


@click.command()
def main() -> int:
    """Console script for naja."""
    click.echo("Replace this message by putting your code into " "naja.cli.main")
    click.echo("See click documentation at https://click.palletsprojects.com/")
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
