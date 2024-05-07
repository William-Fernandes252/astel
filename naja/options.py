from __future__ import annotations

from typing import Type, TypedDict

import httpx
from eventemitter import EventEmitter

from naja import limiters, parsers


class CrawlerOptions(TypedDict, total=False):
    """Crawler options.

    Attributes:
        client (httpx.AsyncClient): An instance of `httpx.AsyncClient` to use for
        network requests.
        workers (int): The number of worker tasks to run in parallel.
        limit (int): The maximum number of pages to crawl.
        user_agent (str): The user agent to use for the requests.
        parser (parsers.Parser): The parser to use for parsing the content of the
        websites to extract links.
        rate_limiter (limiters.RateLimiter): The rate limiter to limit the number of
        requests sent per second.
        event_emitter (EventEmitter): The event emitter to use for emitting events.
    """

    client: httpx.AsyncClient
    workers: int
    limit: int
    user_agent: str
    parser_class: Type[parsers.Parser]
    rate_limiter: limiters.RateLimiter
    event_emitter: EventEmitter


DEFAULT_OPTIONS: CrawlerOptions = {
    "client": httpx.AsyncClient(),
    "workers": 10,
    "limit": 25,
    "user_agent": "naja",
    "parser_class": parsers.HTMLAnchorsParser,
    "rate_limiter": limiters.PerDomainRateLimiter(limiters.StaticRateLimiter(1)),
    "event_emitter": EventEmitter(),
}


def merge_with_default_options(options: CrawlerOptions | None = None) -> CrawlerOptions:
    """Merge the given options with the default options.

    Args:
        options (CrawlerOptions): The options to merge.

    Returns:
        CrawlerOptions: The merged options.
    """
    return {**DEFAULT_OPTIONS, **(options or {})}
