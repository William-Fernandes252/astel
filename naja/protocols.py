from __future__ import annotations

from typing import Set
from urllib.robotparser import RequestRate

from typing_extensions import Protocol

__all__ = ["Filterer", "Parser", "RateLimiter", "Url"]


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


class Filterer(Protocol):
    """
    Filters URLs found by ensuring it passes the requirements to be processed.
    """

    def process(self, url: Url) -> Url | None:
        """
        Filters a URL by ensuring it passes the requirements to be processed. Accepts a base URL and a URL to filter.

        :param base: A string representing the base URL that the filtered URL must start with.
        :type base: `str`

        :param url: An optional string representing the URL to filter.
        :type url: `str | None`

        :return: Either a string representing the filtered URL or None if the provided URL must be ignored.
        :rtype: `str | None`
        """
        ...


class Parser(Protocol):
    """
    Parses the content of a file (webpages, or sitemaps, for example) to extract the links of interest (which are stored in the `found_links` attribute as instances of `Url`).

    :param base: The base URL of the website
    :type base: `str`

    :param url_filter: A Filterer instance that filters the URLs found
    :type url_filter: `Filterer`
    """

    found_links: Set[Url]

    def __init__(self, base: str, *args, **kwargs): ...

    def parse_content(self, text: str) -> None:
        """
        Process the content of a website and update the `found_links` attribute

        :param text: The content to parse
        :type base: `str`
        """
        ...

    @staticmethod
    def parse_url(raw_url: str) -> Url: ...


class RateLimiter(Protocol):
    """
    Limits the amount of concurrent network requests to certain websites in order to avoid bans and throttling.
    """

    def configure(
        self,
        *,
        domain: str | None = None,
        crawl_delay: str | None = None,
        request_rate: RequestRate | None = None,
    ) -> None:
        """
        Configures the rate limiter to respect the rules defined by the domain with the given parameters. In the case of a craw delay, the craw delay is ignored.

        :param domain: A string representing the domain to crawl. Defaults to None.
        :type domain: `str`

        :param request_rate: A RequestRate object representing the rate at which to make requests. Defaults to None.
        :type request_rate: `RequestRate | None`

        :param crawl_delay: A string representing the delay between each crawl in the format "<number><unit>" (as of the format used by `urllib.robotparser`). Defaults to None.
        :type crawl_delay: `str | None`

        :return: `None`
        """
        ...

    async def limit(self, url: str) -> None:
        """
        Asynchronously limits the specified URL.

        :param url: The URL to limit.
        :type url: `str`

        :return: `None`
        :rtype: `None`
        """
        ...
