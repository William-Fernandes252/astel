from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from urllib.robotparser import RequestRate

__all__ = ["Parser", "RateLimiter", "Url"]


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
    """Parses the content of a file (webpages, or sitemaps, for example) to extract
    the links of interest (which are stored in the `found_links`
    attribute as instances of `Url`).

    Args:
        base (str): The base URL to use to resolve relative URLs
    """

    found_links: set[Url]

    def __init__(self, base: str, *args, **kwargs) -> None: ...

    def parse_content(self, text: str) -> None:
        """Process the content of a website and update the `found_links` attribute

        Args:
            text (str): The content of the website
        """
        ...

    @staticmethod
    def parse_url(raw_url: str) -> Url: ...


class RateLimiter(Protocol):
    """
    Limits the amount of concurrent network requests to certain websites
    in order to avoid bans and throttling.
    """

    def configure(
        self,
        *,
        domain: str | None = None,
        crawl_delay: str | None = None,
        request_rate: RequestRate | None = None,
    ) -> None:
        """Configures the rate limiter to respect the rules defined by the
        domain with the given parameters.

        In the case of a craw delay,
        the craw delay is ignored.

        Args:
            domain (str, optional): A string representing the domain to crawl.
            Defaults to None.
            request_rate (RequestRate, optional): A RequestRate object representing
            the rate at which to make requests. Defaults to None.
            crawl_delay (str, optional): A string representing the delay between each
            crawl in the format "<number><unit>" (as of the format used by
            `urllib.robotparser`). Defaults to None.
        """
        ...

    async def limit(self, url: str) -> None:
        """Asynchronously limits the specified URL.

        Args:
            url (str): The URL to limit
        """
        ...
