"""Parsers for extracting links from webpages and sitemaps.

This module defines the parsers that can be used to extract the links from the content of a webpage or a sitemap.
"""  # noqa: E501

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from functools import cached_property
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol, Set
from urllib import parse
from xml.etree import ElementTree

from typing_extensions import override  # type: ignore[attr-defined]


class Url(Protocol):
    """
    Model of a URL for the library to work with.
    """

    @property
    def domain(self) -> str: ...

    @property
    def path(self) -> str: ...

    @property
    def params(self) -> str: ...

    @property
    def scheme(self) -> str: ...

    @property
    def query(self) -> str: ...

    @property
    def fragment(self) -> str: ...

    @property
    def raw(self) -> str: ...

    @property
    def filetype(self) -> str: ...


class Parser(Protocol):
    """Parses the content of a file (webpages, or sitemaps, for example) to extract the links of interest.

    Args:
        base (Union[str, None]): The base URL to use to resolve relative URLs. Defaults to `None`.
    """  # noqa: E501

    def __init__(self, base: str | None = None) -> None: ...

    def feed(self, text: str) -> None:
        """Process the content of a website and update the `found_links` attribute

        Args:
            text (str): The content of the website
        """
        ...

    def reset(self, base: str | None = None) -> None:
        """Reset the parser to its initial state.

        Args:
            base (Union[str, None], optional): The base URL to use to resolve relative URLs. Defaults to `None`.
        """  # noqa: E501

    @property
    def base(self) -> str | None: ...

    @property
    def found_links(self) -> Set[Url]: ...


@dataclass(frozen=True)
class ParsedUrl:
    scheme: str
    domain: str
    path: str
    params: str
    query: str
    fragment: str

    @cached_property
    def raw(self) -> str:
        return parse.urlunparse(
            (
                self.scheme,
                self.domain,
                self.path,
                self.params,
                self.query,
                self.fragment,
            )
        )

    @cached_property
    def filetype(self) -> str:
        return Path(self.path).suffix.replace(".", "")


def parse_url(url: str, base: str | None = None) -> Url:
    """Parse a URL into its components.

    Args:
        url (str): The URL to parse
        base (str, optional): The base URL to use to resolve relative URLs. Defaults to `None`.

    Returns:
        Url: The parsed URL
    """  # noqa: E501
    result = parse.urlparse(url if base is None else parse.urljoin(base, url))
    return ParsedUrl(
        result.scheme,
        result.netloc,
        result.path,
        result.params,
        result.query,
        result.fragment,
    )


class InitParserMixin:
    """Helper mixin to initialize the parser with a base URL."""

    def __init__(self, base: str | None = None) -> None:
        self.base = base
        self.found_links: Set[Url] = set()
        super().__init__()

    def reset(self, base: str | None = None) -> None:
        if base is not None:
            self.base = base
        self.found_links.clear()
        getattr(super(), "reset", lambda: ...)()


class BaseParser(InitParserMixin, ABC):
    """Base class to be used for implementing new parser classes."""


class HTMLAnchorsParser(InitParserMixin, HTMLParser):
    """A parser that extracts the urls from a webpage and filter them out with the
    given filterer.

    Args:
        base (str): The base URL to use to resolve relative URLs
    """

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return

        for attr, value in attrs:
            if attr == "href" and isinstance(value, str):
                self.found_links.add(parse_url(value, self.base))


class SiteMapParser(InitParserMixin):
    """Parses a sitemap file to extract the links of interest.

    Args:
        base (str): The base URL to use to resolve relative URLs
    """

    def feed(self, text: str) -> None:
        root = ElementTree.fromstring(text)

        for url_element in root.iter(
            "{http://www.sitemaps.org/schemas/sitemap/0.9}url"
        ):
            loc_element = url_element.find(
                "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
            )
            if loc_element is not None and loc_element.text:
                self.found_links.add(parse_url(loc_element.text))
