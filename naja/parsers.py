from html.parser import HTMLParser

from .protocols import Filterer


class UrlParser(HTMLParser):
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
        self.found_links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return

        for attr, url in attrs:
            if attr != "href":
                continue

        if (url := self.url_filter.filter_url(self.base, url)) is not None:
            self.found_links.add(url)

    def parse(self, text: str) -> None:
        super().feed(text)
