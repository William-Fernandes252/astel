from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from html.parser import HTMLParser
from pathlib import Path
from urllib import parse
from xml.etree import ElementTree as ET

from .protocols import Filterer, Url


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


class UrlParserMixin:
    @staticmethod
    def parse_url(url: str) -> Url:
        result = parse.urlparse(url)
        return ParsedUrl(
            result.scheme,
            result.netloc,
            result.path,
            result.params,
            result.query,
            result.fragment,
        )


class HTMLAnchorsParser(HTMLParser, UrlParserMixin):
    """
    A parser that extracts the urls from a webpage and filter them out with the given filterer

    :param base: The base URL of the webpage
    :type base: `str`

    :param url_filter: A `Filterer` instance that filters the URLs found
    :type url_filter: `Filterer`
    """

    def __init__(self, base: str, url_filter: Filterer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base = base
        self.url_filter = url_filter
        self.found_links: set[Url] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return

        for attr, value in attrs:
            if attr == "href" and type(value) is str:
                if (
                    parsed_url := self.url_filter.process(self.parse_url(value))
                ) is not None:
                    self.found_links.add(parsed_url)

    def parse_content(self, text: str) -> None:
        super().feed(text)


class SiteMapParser(UrlParserMixin):
    def __init__(self, base: str, url_filter: Filterer, *args, **kwargs):
        self.base = base
        self.url_filter = url_filter
        self.found_links: set[Url] = set()

    def parse_content(self, text: str) -> None:
        root = ET.fromstring(text)

        for url_element in root.iter(
            "{http://www.sitemaps.org/schemas/sitemap/0.9}url"
        ):
            loc_element = url_element.find(
                "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
            )
            if loc_element is not None and loc_element.text:
                self.found_links.add(self.parse_url(loc_element.text))
