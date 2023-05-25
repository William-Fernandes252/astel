import asyncio
import time
from functools import partial
from typing import Callable

import tldextract

from . import errors, protocols

__all__ = [
    "StaticRateLimiter",
    "NoLimitRateLimiter",
    "TokenBucketRateLimiter",
    "PeriodicRateLimiter",
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


class NoLimitRateLimiter:
    """
    A limiter that does not limit the requests. Keep in mind that sending a lot of requests per second can result in throttling or even bans.
    """

    async def limit(self, *args, **kwargs) -> None:
        """
        Asynchronously sleeps for 0 seconds.
        """
        await asyncio.sleep(0)


class TokenBucketRateLimiter:
    """
    A rate limiter that limits the requests by using the token bucket algorithm

    :param tokens_per_second: The number of tokens per second
    :type tokens_per_second: `int`
    """

    def __init__(self, tokens_per_second: int):
        self.tokens_per_second = tokens_per_second
        self.tokens = 0
        self.last_refresh_time = time.time()

    def _refresh_tokens(self) -> None:
        """
        Refreshes the tokens in the bucket based on the time elapsed since the last refresh
        """
        current_time = time.time()
        time_elapsed = current_time - self.last_refresh_time
        new_tokens = time_elapsed * self.tokens_per_second
        self.tokens = int(min(self.tokens + new_tokens, self.tokens_per_second))
        self.last_refresh_time = current_time

    def consume(self, tokens: int = 1) -> bool:
        """
        Check if the given number of tokens can be consumed and decrease the number of available tokens if possible.

        :param tokens: An integer representing the number of tokens to consume. Default is 1.
        :type tokens: `int`

        :return: A boolean value indicating whether the tokens were successfully consumed or not.
        :rtype: `bool`
        """
        self._refresh_tokens()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    async def limit(self, *args, **kwargs) -> None:
        while not self.consume(1):
            pass


class PerDomainRateLimiter:
    """
    Rate limiter that limits the number of requests per domain using its especified limiter instance if given, otherwise uses the default limiter

    :param limiter_factory: A callable that creates a limiter instance (defaults to `StaticRateLimiter` with a 1 second delay between requests)
    :type limiter_factory: `Callable[[], protocols.BaseLimiter]`
    """

    __slots__ = {"default_limiter_factory", "domain_to_limiter"}

    def __init__(
        self,
        limiter_factory: Callable[[], protocols.RateLimiter] = partial(
            StaticRateLimiter, 1
        ),
    ) -> None:
        self.default_limiter_factory = limiter_factory
        self.domain_to_limiter: dict[str, protocols.RateLimiter] = {}

    async def limit(self, url: str, *args, **kwargs) -> None:
        """Limit by wainting for the limiting of the limiter instance corresponding to the domain of the given url"""
        await self.domain_to_limiter.get(
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

        self.domain_to_limiter[domain] = limiter or self.default_limiter_factory()

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
