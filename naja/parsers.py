from html.parser import HTMLParser
from urllib import parse
from xml.etree import ElementTree as ET

from .protocols import Filterer


class HTMLAnchorsParser(HTMLParser):
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
        self.found_links: set[parse.ParseResult] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return

        for attr, url in attrs:
            if attr != "href":
                continue

        if (url := self.url_filter.filter_url(self.base, url)) is not None:
            self.found_links.add(parse.urlparse(url))

    def parse_content(self, text: str) -> None:
        super().feed(text)

    @staticmethod
    def parse_url(url: str) -> parse.ParseResult:
        return parse.urlparse(url)


class SiteMapParser:
    def __init__(self, base: str, url_filter: Filterer, *args, **kwargs):
        self.base = base
        self.url_filter = url_filter
        self.found_links: set[parse.ParseResult] = set()

    def parse_content(self, text: str) -> None:
        root = ET.fromstring(text)

        for url_element in root.iter(
            "{http://www.sitemaps.org/schemas/sitemap/0.9}url"
        ):
            loc_element = url_element.find(
                "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
            )
            if loc_element is not None and loc_element.text:
                self.found_links.add(parse.urlparse(loc_element.text))
