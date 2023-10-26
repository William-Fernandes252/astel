from __future__ import annotations

import asyncio
import time
from functools import partial
from typing import Callable
from urllib.robotparser import RequestRate

import tldextract

from . import errors, protocols

__all__ = [
    "StaticRateLimiter",
    "NoLimitRateLimiter",
    "TokenBucketRateLimiter",
    "PerDomainRateLimiter",
]


class StaticRateLimiter:
    """
    Static rate limiter that limits the number of requests per second by waiting for a specified amount of time between requests

    :param time_in_seconds: The amount of time (in seconds) to wait between requests
    :type time_in_seconds: `float`
    """

    def __init__(self, time_in_seconds: float) -> None:
        self.time = time_in_seconds

    async def limit(self, *args, **kwargs) -> None:
        """Limit by wainting for the specified amount of time"""
        await asyncio.sleep(self.time)

    def configure(
        self,
        *,
        crawl_delay: str | None = None,
        request_rate: RequestRate | None = None,
        **kwargs,
    ) -> None:
        if crawl_delay is not None:
            new_request_delay = float(crawl_delay)
        elif request_rate is not None:
            new_request_delay = request_rate.seconds / request_rate.requests

        if new_request_delay < 0:
            raise errors.InvalidConfigurationError(
                f"The new request delay must be greater than 0 (got {new_request_delay})."
            )

        # Use the greater of the two in order to respect all the domains
        if new_request_delay > self.time:
            self.time = new_request_delay


class NoLimitRateLimiter:
    """
    A limiter that does not limit the requests. Keep in mind that sending a lot of requests per second can result in throttling or even bans.
    """

    async def limit(self, *args, **kwargs) -> None:
        """
        Asynchronously sleeps for 0 seconds.
        """
        await asyncio.sleep(0)

    def configure(self, *args, **kwargs) -> None:
        """
        Does nothing
        """
        pass


class TokenBucketRateLimiter:
    """
    A rate limiter that limits the requests by using the token bucket algorithm

    :param tokens_per_second: The number of tokens per second
    :type tokens_per_second: `float`
    """

    __slots__ = ("_tokens_per_second", "_tokens", "_last_refresh_time")

    def __init__(self, tokens_per_second: float):
        if tokens_per_second <= 0:
            raise ValueError("tokens_per_second must be greater than 0")

        self._tokens_per_second = tokens_per_second
        self._tokens = 0.0
        self._last_refresh_time = time.time()

    def _refresh_tokens(self) -> None:
        """
        Refreshes the tokens in the bucket based on the time elapsed since the last refresh
        """
        current_time = time.time()
        time_elapsed = current_time - self._last_refresh_time
        new_tokens = time_elapsed * self._tokens_per_second
        self._tokens = float(min(self._tokens + new_tokens, self._tokens_per_second))
        self._last_refresh_time = current_time

    def consume(self, tokens: int = 1) -> bool:
        """
        Check if the given number of tokens can be consumed and decrease the number of available tokens if possible.

        :param tokens: An integer representing the number of tokens to consume. Default is 1.
        :type tokens: `int`

        :return: A boolean value indicating whether the tokens were successfully consumed or not.
        :rtype: `bool`
        """
        self._refresh_tokens()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    async def limit(self, *args, **kwargs) -> None:
        while not self.consume(1):
            pass

    @property
    def tokens(self):
        return self._tokens

    @property
    def tokens_per_second(self):
        return self._tokens_per_second

    @property
    def last_refresh_time(self):
        return self._last_refresh_time

    def configure(
        self,
        *,
        crawl_delay: str | None = None,
        request_rate: RequestRate | None = None,
        **kwargs,
    ) -> None:
        """
        Configures the rate at which requests are made to a domain by setting the tokens per second.

        :param crawl_delay: The amount of time (in seconds) to wait between requests
        :type crawl_delay: `str`

        :param request_rate: The rate at which requests are made to a domain
        :type request_rate: `RequestRate`

        :raises `InvalidConfigurationError`: If the new computed token rate is less than or equal to 0.

        :return: `None`
        """
        if crawl_delay is not None:
            new_token_rate = 1 / int(crawl_delay)
        elif request_rate is not None:
            new_token_rate = request_rate.requests / request_rate.seconds
        else:
            return

        if new_token_rate < 0:
            raise errors.InvalidConfigurationError(
                f"The new token rate must be greater than 0 (got {new_token_rate})."
            )

        # Update the tokens per second to be the smallest of the two, in order to respect every domain's rules
        if new_token_rate < self._tokens_per_second:
            self._tokens_per_second = new_token_rate


class PerDomainRateLimiter:
    """
    Rate limiter that limits the number of requests per domain using its especified limiter instance if given, otherwise uses the default limiter

    :param limiter_factory: A callable that creates a limiter instance (defaults to `StaticRateLimiter` with a 1 second delay between requests)
    :type limiter_factory: `Callable[[], protocols.BaseLimiter]`
    """

    __slots__ = {"default_limiter_factory", "_domain_to_limiter"}

    def __init__(
        self,
        limiter_factory: Callable[[], protocols.RateLimiter] = partial(
            StaticRateLimiter, time_in_seconds=1
        ),
    ) -> None:
        self.default_limiter_factory = limiter_factory
        self._domain_to_limiter: dict[str, protocols.RateLimiter] = {}

    async def limit(self, url: str, *args, **kwargs) -> None:
        """Limit by waiting for the limiting of the limiter instance corresponding to the domain of the given url"""
        await self._domain_to_limiter.get(
            self.extract_domain(url), self.default_limiter_factory()
        ).limit(url, *args, **kwargs)

    def add_domain(
        self, url: str, limiter: protocols.RateLimiter | None = None
    ) -> None:
        """
        Adds a new domain to the limited domains with an optional rate limiter.

        :param url: A string representing the URL to extract the domain from.
        :type url: `str`

        :param limiter: An optional `BaseLimiter` instance used to limit the rate of requests to the domain.
        :type limiter: `BaseLimiter | None`

        :raises: `InvalidUrlError` if the given URL does not contain a valid domain.

        :return: `None`
        """
        domain = self.extract_domain(url)
        if domain == "":
            raise errors.InvalidUrlError(url)

        self._domain_to_limiter[domain] = limiter or self.default_limiter_factory()

    @staticmethod
    def extract_domain(url: str) -> str:
        """
        Extracts the domain from a given URL.

        :param url: A string representing a URL.
        :type url: `str`

        :return: A string representing the domain name extracted from the URL.
        :rtype: `str`
        """
        return tldextract.extract(url).domain

    def configure(
        self,
        *,
        domain: str,
        crawl_delay: str | None = None,
        request_rate: RequestRate | None = None,
        **kwargs,
    ) -> None:
        """
        Configures the rate at which requests are made to a domain by configurering its corresponding limiter.

        :param domain: A string representing the domain name to configure the limiter for.
        :type domain: `str`

        :param crawl_delay: The amount of time (in seconds) to wait between requests
        :type crawl_delay: `str`

        :param request_rate: The rate at which requests are made to a domain
        :type request_rate: `RequestRate`

        :raises `InvalidConfigurationError`: If domain is not provided, or neither crawl_delay nor request_rate is provided or if the new computed token rate is less than or equal to 0.
        """
        if domain is None:
            raise errors.InvalidConfigurationError("A domain must be provided.")

        if domain not in self._domain_to_limiter:
            self.add_domain(domain)

        return self._domain_to_limiter[domain].configure(
            crawl_delay=crawl_delay, request_rate=request_rate, **kwargs
        )

    @property
    def domain_to_limiter(self) -> dict[str, protocols.RateLimiter]:
        return self._domain_to_limiter
