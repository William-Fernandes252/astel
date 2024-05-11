from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, TypedDict, cast

import tldextract

from . import errors

if TYPE_CHECKING:
    from urllib.robotparser import RequestRate  # type: ignore[attr-defined]

__all__ = [
    "RateLimiter",
    "StaticRateLimiter",
    "NoLimitRateLimiter",
    "TokenBucketRateLimiter",
    "PerDomainRateLimiter",
]


class RateLimiterConfig(TypedDict, total=False):
    """Rate limiting configuration.

    Attributes:
        domain (str): The domain to crawl.
        crawl_delay (str, optional): A string representing the delay between each
        crawl in the format "<number><unit>" (as of the format used by
        request_rate (RequestRate): The rate at which to make requests.
    """

    domain: Optional[str]
    crawl_delay: Optional[str]
    request_rate: Optional[RequestRate]


class RateLimiter(ABC):
    """
    Limits the amount of concurrent network requests to certain websites
    in order to avoid bans and throttling.
    """

    @abstractmethod
    def configure(
        self,
        config: RateLimiterConfig,
    ) -> None:
        """Configures the rate limiter to respect the rules defined by the
        domain with the given parameters.

        In the case of a craw delay, the craw delay is ignored.

        Args:
            config (RateLimiterConfig): The configuration to apply.
        """
        ...

    @abstractmethod
    async def limit(self, *args, **kwargs) -> None:
        """Asynchronously limits the specified URL.

        Args:
            url (str): The URL to limit
        """
        ...


class StaticRateLimiter(RateLimiter):
    """Limit the number of requests per second by waiting for a
    specified amount of time between requests

    Args:
        time_in_seconds (float): The amount of time to wait between requests
    """

    def __init__(self, time_in_seconds: float) -> None:
        self.time = time_in_seconds

    async def limit(self) -> None:  # type: ignore[override]
        """Limit by wainting for the specified amount of time"""
        await asyncio.sleep(self.time)

    def configure(
        self,
        config: RateLimiterConfig,
    ) -> None:
        new_request_delay: Optional[float] = None
        if craw_delay := config.get("crawl_delay", None):
            new_request_delay = float(craw_delay)
        elif request_rate := config.get("request_rate", None):
            new_request_delay = request_rate.seconds / request_rate.requests

        if new_request_delay and new_request_delay < 0:
            msg = "The new request delay must be greater "
            "than 0 (got {new_request_delay})."
            raise errors.InvalidConfigurationError(msg)

        # Use the greater of the two in order to respect all the domains
        if new_request_delay and new_request_delay > self.time:
            self.time = new_request_delay


class NoLimitRateLimiter(RateLimiter):
    """
    A limiter that does not limit the requests. Keep in mind that sending a
    lot of requests per second can result in throttling or even bans.
    """

    async def limit(self) -> None:  # type: ignore[override]
        """
        Asynchronously sleeps for 0 seconds.
        """
        await asyncio.sleep(0)

    def configure(self, *args, **kwargs) -> None:
        """
        Does nothing
        """


class TokenBucketRateLimiter(RateLimiter):
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
        self._last_refresh_time = self.utcnow()

    @staticmethod
    def utcnow() -> datetime:
        return datetime.now(timezone.utc)

    def _refresh_tokens(self) -> None:
        """Refreshes the tokens in the bucket based on the time elapsed since
        the last refresh
        """
        current_time = self.utcnow()
        time_elapsed = current_time - self._last_refresh_time
        new_tokens = time_elapsed.seconds * self._tokens_per_second
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

    async def limit(self) -> None:  # type: ignore[override]
        while not self.consume(1):
            pass

    @property
    def tokens(self) -> float:
        self._refresh_tokens()
        return self._tokens

    @property
    def tokens_per_second(self) -> float:
        return self._tokens_per_second

    @property
    def last_refresh_time(self) -> datetime:
        return self._last_refresh_time

    def configure(
        self,
        config: RateLimiterConfig,
    ) -> None:
        """Configures the rate at which requests are made to a domain by setting the
        tokens per second.
        """
        if config["crawl_delay"] is not None:
            new_token_rate = 1 / int(config["crawl_delay"])
        elif config["request_rate"] is not None:
            new_token_rate = (
                config["request_rate"].requests / config["request_rate"].seconds
            )
        else:
            return

        if new_token_rate < 0:
            msg = f"The new token rate must be greater than 0 (got {new_token_rate})."
            raise errors.InvalidConfigurationError(msg)

        if new_token_rate < self._tokens_per_second:
            self._tokens_per_second = new_token_rate


class PerDomainRateLimiter(RateLimiter):
    """Limit the number of requests per domain using its especified
    limiter instance if given, otherwise uses the default limiter
    """

    default_limiter: RateLimiter | None = None
    _domain_to_limiter: dict[str, RateLimiter]

    def __init__(
        self,
        default_limiter: RateLimiter | None = None,
    ) -> None:
        self.default_limiter = default_limiter
        self._domain_to_limiter = {}

    async def limit(self, url: str) -> None:  # type: ignore[override]
        """Limit the requests to the given URL by its domain.

        Args:
            url (str): The URL to limit

        Raises:
            errors.InvalidConfigurationError: If no limiter is found for the domain.
        """
        limiter = self._domain_to_limiter.get(
            self.extract_domain(url), self.default_limiter
        )
        if limiter is None:
            msg = "No limiter found for the domain."
            raise errors.InvalidConfigurationError(msg)

        await limiter.limit()

    def add_domain(self, domain: str, limiter: RateLimiter | None = None) -> None:
        """Adds a new domain to the limited domains with an optional rate limiter.

        Args:
            domain (str): A string representing the domain name to add.
            limiter (protocols.RateLimiter, optional): An optional `RateLimiter`
            instance used to limit the rate of requests to the domain. Defaults to None.

        Raises:
            errors.InvalidUrlError: If the given URL does not contain a valid domain.
        """
        if limiter is None and self.default_limiter is None:
            msg = "No limiter was provided and no default limiter was set."
            raise errors.InvalidConfigurationError(msg)

        self._domain_to_limiter[domain] = cast(
            RateLimiter, limiter or self.default_limiter
        )

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extracts the domain from a given URL.

        Returns:
            str: A string representing the domain name extracted from the URL.
        """
        return tldextract.extract(url).domain

    def configure(self, config: RateLimiterConfig) -> None:
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
        if (
            config["domain"] is not None
            and config["domain"] not in self._domain_to_limiter
        ):
            self.add_domain(config["domain"])
            self._domain_to_limiter[config["domain"]].configure(config)

    @property
    def domain_to_limiter(self) -> dict[str, RateLimiter]:
        return self._domain_to_limiter
