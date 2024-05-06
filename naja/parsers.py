from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol, Set
from urllib import parse
from xml.etree import ElementTree


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


class Parser(ABC):
    """Parses the content of a file (webpages, or sitemaps, for example) to extract
    the links of interest (which are stored in the `found_links`
    attribute as instances of `Url`).

    Args:
        base (str): The base URL to use to resolve relative URLs
    """

    found_links: Set[Url]

    @abstractmethod
    def __init__(self, base: str, *args, **kwargs) -> None: ...

    @abstractmethod
    def parse_content(self, text: str) -> None:
        """Process the content of a website and update the `found_links` attribute

        Args:
            text (str): The content of the website
        """
        ...


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


def parse_url(url: str) -> Url:
    """Parse a URL into its components.

    Args:
        url (str): The URL to parse

    Returns:
        Url: The parsed URL
    """
    result = parse.urlparse(url)
    return ParsedUrl(
        result.scheme,
        result.netloc,
        result.path,
        result.params,
        result.query,
        result.fragment,
    )


class HTMLAnchorsParser(HTMLParser, Parser):
    """A parser that extracts the urls from a webpage and filter them out with the
    given filterer.

    Args:
        base (str): The base URL to use to resolve relative URLs
        url_filter (Filterer): The filterer to use to filter the URLs
    """

    def __init__(self, base: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.base = base
        self.found_links: set[Url] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return

        for attr, value in attrs:
            if attr == "href" and isinstance(value, str):
                self.found_links.add(parse_url(value))

    def parse_content(self, text: str) -> None:
        super().feed(text)


class SiteMapParser(Parser):
    """Parses a sitemap file to extract the links of interest.

    Args:
        base (str): The base URL to use to resolve relative URLs
    """

    def __init__(self, base: str) -> None:
        self.base = base
        self.found_links: set[Url] = set()

    def parse_content(self, text: str) -> None:
        root = ElementTree.fromstring(text)

        for url_element in root.iter(
            "{http://www.sitemaps.org/schemas/sitemap/0.9}url"
        ):
            loc_element = url_element.find(
                "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
            )
            if loc_element is not None and loc_element.text:
                self.found_links.add(parse_url(loc_element.text))
