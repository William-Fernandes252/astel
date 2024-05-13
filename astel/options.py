"""Options module.

This module defines the options that can be used to configure the crawlers behavior.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable, Protocol, Type, TypedDict, Union

import eventemitter
import httpx

from astel import events, limiters, parsers

if TYPE_CHECKING:
    from astel.crawler import Crawler


class RetryHandler(Protocol):
    """Callable that determines whether the crawler should retry the request."""

    def __call__(
        self, url: parsers.Url, response: Union[httpx.Response, None], crawler: Crawler
    ) -> bool: ...


class CrawlerOptions(TypedDict, total=False):
    """Crawler options.

    Attributes:
        client (httpx.AsyncClient): An instance of `httpx.AsyncClient` to use for network requests.
        workers (int): The number of worker tasks to run in parallel.
        limit (int): The maximum number of pages to crawl.
        user_agent (str): The user agent to use for the requests.
        parser (parsers.Parser): The parser to use for parsing the content of the websites to extract links.
        rate_limiter (limiters.RateLimiter): The rate limiter to limit the number of requests sent per second.
        event_limiter_factory (Callable[[], events.EventEmitter]): A factory function to create an event limiter for the crawler.
        retry_for_status_codes (list[int]): A list of status codes for which the crawler should retry the request.
    """  # noqa: E501

    client: httpx.AsyncClient
    workers: int
    limit: int
    user_agent: str
    parser_class: Type[parsers.Parser]
    rate_limiter: limiters.RateLimiter
    event_emitter_factory: Callable[[], events.EventEmitter]
    retry_for_status_codes: list[int]


DEFAULT_OPTIONS: CrawlerOptions = {
    "client": httpx.AsyncClient(),
    "workers": 10,
    "limit": 25,
    "user_agent": "astel",
    "parser_class": parsers.HTMLAnchorsParser,
    "rate_limiter": limiters.PerDomainRateLimiter(limiters.StaticRateLimiter(1)),
    "event_emitter_factory": lambda: eventemitter.EventEmitter(
        asyncio.get_event_loop()
    ),
    "retry_for_status_codes": [],
}


def merge_with_default_options(options: CrawlerOptions | None = None) -> CrawlerOptions:
    """Merge the given options with the default options.

    Args:
        options (CrawlerOptions): The options to merge.

    Returns:
        CrawlerOptions: The merged options.
    """
    return {**DEFAULT_OPTIONS, **(options or {})}  # type: ignore   # noqa: PGH003
