from __future__ import annotations

import asyncio
import time
from functools import partial
from typing import TYPE_CHECKING

import tldextract

from . import errors, protocols

if TYPE_CHECKING:
    from collections.abc import Callable
    from urllib.robotparser import RequestRate

__all__ = [
    "StaticRateLimiter",
    "NoLimitRateLimiter",
    "TokenBucketRateLimiter",
    "PerDomainRateLimiter",
]


class StaticRateLimiter:
    """Limit the number of requests per second by waiting for a
    specified amount of time between requests

    Args:
        time_in_seconds (float): The amount of time to wait between requests
    """

    def __init__(self, time_in_seconds: float) -> None:
        self.time = time_in_seconds

    async def limit(self, url) -> None:  # noqa: ANN001, ARG002
        """Limit by wainting for the specified amount of time"""
        await asyncio.sleep(self.time)

    def configure(
        self,
        *,
        crawl_delay: str | None = None,
        request_rate: RequestRate | None = None,
    ) -> None:
        if crawl_delay is not None:
            new_request_delay = float(crawl_delay)
        elif request_rate is not None:
            new_request_delay = request_rate.seconds / request_rate.requests

        if new_request_delay < 0:
            msg = "The new request delay must be greater "
            "than 0 (got {new_request_delay})."
            raise errors.InvalidConfigurationError(msg)

        # Use the greater of the two in order to respect all the domains
        if new_request_delay > self.time:
            self.time = new_request_delay


class NoLimitRateLimiter:
    """
    A limiter that does not limit the requests. Keep in mind that sending a
    lot of requests per second can result in throttling or even bans.
    """

    async def limit(self) -> None:
        """
        Asynchronously sleeps for 0 seconds.
        """
        await asyncio.sleep(0)

    def configure(self) -> None:
        """
        Does nothing
        """


class TokenBucketRateLimiter:
    """Limit the requests by using the token bucket algorithm

    Args:
        tokens_per_second (float): The amount of tokens to add to the bucket
        per second
    """

    __slots__ = ("_tokens_per_second", "_tokens", "_last_refresh_time")

    def __init__(self, tokens_per_second: float) -> None:
        if tokens_per_second <= 0:
            msg = "tokens_per_second must be greater than 0"
            raise ValueError(msg)

        self._tokens_per_second = tokens_per_second
        self._tokens = 0.0
        self._last_refresh_time = time.time()

    def _refresh_tokens(self) -> None:
        """
        Refreshes the tokens in the bucket based on the time elapsed since the
        last refresh
        """
        current_time = time.time()
        time_elapsed = current_time - self._last_refresh_time
        new_tokens = time_elapsed * self._tokens_per_second
        self._tokens = float(min(self._tokens + new_tokens, self._tokens_per_second))
        self._last_refresh_time = current_time

    def consume(self, tokens: int = 1) -> bool:
        """Check if the given number of tokens can be consumed and decrease the
        number of available tokens if possible.

        Args:
            tokens (int, optional): The number of tokens to consume. Default is 1.

        Returns:
            bool: `True` if the tokens were consumed, `False` otherwise
        """
        self._refresh_tokens()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    async def limit(self) -> None:
        while not self.consume(1):
            pass

    @property
    def tokens(self) -> float:
        return self._tokens

    @property
    def tokens_per_second(self) -> float:
        return self._tokens_per_second

    @property
    def last_refresh_time(self) -> float:
        return self._last_refresh_time

    def configure(
        self,
        *,
        crawl_delay: str | None = None,
        request_rate: RequestRate | None = None,
    ) -> None:
        """Configures the rate at which requests are made to a domain by setting the
        tokens per second.

        Args:
            crawl_delay (str, optional): The amount of time (in seconds) to wait between
            requests. Defaults to None.
            request_rate (RequestRate, optional): The rate at which requests are made to
            a domain. Defaults to None.

        Raises:
            errors.InvalidConfigurationError: If the new computed token rate is less
            than or equal to 0.
        """
        if crawl_delay is not None:
            new_token_rate = 1 / int(crawl_delay)
        elif request_rate is not None:
            new_token_rate = request_rate.requests / request_rate.seconds
        else:
            return

        if new_token_rate < 0:
            msg = f"The new token rate must be greater than 0 (got {new_token_rate})."
            raise errors.InvalidConfigurationError(msg)

        if new_token_rate < self._tokens_per_second:
            self._tokens_per_second = new_token_rate


class PerDomainRateLimiter:
    """Limit the number of requests per domain using its especified
    limiter instance if given, otherwise uses the default limiter
    """

    __slots__ = {"default_limiter_factory", "_domain_to_limiter"}

    DEFAULT_LIMITER_FACTORY: Callable[[], protocols.RateLimiter] = partial(
        StaticRateLimiter, time_in_seconds=1  # type: ignore[assignment]
    )

    def __init__(
        self,
        limiter_factory: Callable[[], protocols.RateLimiter] | None = None,
    ) -> None:
        self.default_limiter_factory = limiter_factory or self.DEFAULT_LIMITER_FACTORY
        self._domain_to_limiter: dict[str, protocols.RateLimiter] = {}

    async def limit(self, url: str) -> None:
        """Limit by waiting for the limiting of the limiter instance corresponding to
        the domain of the given url"""
        await self._domain_to_limiter.get(
            self.extract_domain(url), self.default_limiter_factory()
        ).limit(url)

    def add_domain(
        self, url: str, limiter: protocols.RateLimiter | None = None
    ) -> None:
        """Adds a new domain to the limited domains with an optional rate limiter.

        Args:
            url (str): A string representing the URL to extract the domain from.
            limiter (protocols.RateLimiter, optional): An optional `RateLimiter`
            instance used to limit the rate of requests to the domain. Defaults to None.

        Raises:
            errors.InvalidUrlError: If the given URL does not contain a valid domain.
        """
        domain = self.extract_domain(url)
        if domain == "":
            raise errors.InvalidUrlError(url)

        self._domain_to_limiter[domain] = limiter or self.default_limiter_factory()

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extracts the domain from a given URL.

        Returns:
            str: A string representing the domain name extracted from the URL.
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
        """Configures the rate at which requests are made to a domain by defining its
        corresponding limiter.

        Args:
            domain (str): A string representing the domain name to configure
            the limiter for.
            crawl_delay (str, optional): The amount of time (in seconds) to wait
            between requests. Defaults to None.
            request_rate (RequestRate, optional): The rate at which requests are made
            to a domain. Defaults to None.

        Raises:
            errors.InvalidConfigurationError: If the new computed token rate is less
            than or equal to 0.
        """
        if domain not in self._domain_to_limiter:
            self.add_domain(domain)

        return self._domain_to_limiter[domain].configure(
            crawl_delay=crawl_delay, request_rate=request_rate, **kwargs
        )

    @property
    def domain_to_limiter(self) -> dict[str, protocols.RateLimiter]:
        return self._domain_to_limiter
