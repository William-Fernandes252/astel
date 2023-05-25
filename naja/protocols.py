from typing import Protocol

__all__ = [
    "Filterer",
    "Parser",
    "RateLimiter",
]


class Filterer(Protocol):
    """
    Filters URLs found by ensuring it passes the requirements to be processed.
    """

    def filter_url(self, base: str, url: str | None) -> str | None:
        """
        Filters a URL by ensuring it passes the requirements to be processed. Accepts a base URL and a URL to filter.

        :param base: A string representing the base URL that the filtered URL must start with.
        :param url: An optional string representing the URL to filter.

        :return: Either a string representing the filtered URL or None if the provided URL must be ignored.
        """
        ...


class Parser(Protocol):
    """
    Parsers the content of a website to extract links of interest (which are stored in the ``found_links`` attribute).

    :param base: The base URL of the website
    :type base: str
    :param url_filter: A BaseFilterer instance that filters the URLs found
    :type url_filter: BaseFilterer
    """

    found_links: set[str]

    def __init__(self, base: str, url_filter: Filterer, *args, **kwargs):
        ...

    def parse(self, text: str) -> None:
        """
        Process the content of a website and update the ``found_links`` attribute

        :param text: The content to parse
        :type base: str
        """
        ...


