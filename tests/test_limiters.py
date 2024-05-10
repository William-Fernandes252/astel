import asyncio
from typing import ClassVar, Union
from urllib.robotparser import RequestRate

import pytest
from freezegun import freeze_time
from hypothesis import given, provisional
from pytest_mock import MockerFixture, MockType

from naja import errors, limiters


class DescribeStaticLimiter:
    @pytest.fixture()
    def limiter(self):
        return limiters.StaticRateLimiter(0.5)

    async def it_limits_by_waiting_for_the_specified_amount_of_time(
        self, limiter: limiters.StaticRateLimiter, mocker: MockerFixture
    ):
        spy = mocker.spy(asyncio, "sleep")
        await limiter.limit()
        spy.assert_called_once_with(0.5)

    @pytest.mark.parametrize(("crawl_delay", "expected"), [("1", 1), ("0.5", 0.5)])
    async def it_sets_the_new_time_from_craw_delay(
        self, limiter: limiters.StaticRateLimiter, crawl_delay: str, expected: float
    ):
        config: limiters.RateLimiterConfig = {"crawl_delay": crawl_delay}
        limiter.configure(config)
        assert limiter.time == expected

    @pytest.mark.parametrize(("request_rate", "expected"), [(RequestRate(1, 2), 2)])
    async def it_sets_the_new_time_from_request_rate(
        self,
        limiter: limiters.StaticRateLimiter,
        request_rate: RequestRate,
        expected: float,
    ):
        config: limiters.RateLimiterConfig = {"request_rate": request_rate}
        limiter.configure(config)
        assert limiter.time == expected


class DescribeNoLimitRateLimiter:
    @pytest.fixture()
    def limiter(self):
        return limiters.NoLimitRateLimiter()

    async def it_does_not_limit(
        self, limiter: limiters.NoLimitRateLimiter, mocker: MockerFixture
    ):
        spy = mocker.spy(asyncio, "sleep")
        await limiter.limit()
        spy.assert_called_once_with(0)


class DescribeTokenBucketRateLimiter:
    def it_consumes_if_there_is_any(self):
        with freeze_time("2021-01-01") as frozen_time:
            limiter = limiters.TokenBucketRateLimiter(5)
            frozen_time.tick()
            initial_tokens = limiter.tokens
            assert limiter.consume()
            assert limiter.tokens == initial_tokens - 1

    def it_does_not_consume_if_there_are_no_tokens(self):
        limiter = limiters.TokenBucketRateLimiter(1)
        assert not limiter.consume()

    async def it_limits_by_consuming_a_token(self):
        with freeze_time("2021-01-01") as frozen_time:
            limiter = limiters.TokenBucketRateLimiter(5)
            frozen_time.tick()
            initial_tokens = limiter.tokens
            await limiter.limit()
            assert limiter.tokens == initial_tokens - 1


class DescribePerDomainRateLimiter:
    class CaseNoDomain:
        @pytest.fixture(scope="class")
        def limiter(self):
            return limiters.PerDomainRateLimiter()

        @pytest.fixture()
        def limiter_with_default(self, mocker: MockerFixture):
            return limiters.PerDomainRateLimiter(mocker.MagicMock(limiters.RateLimiter))

        @given(url=provisional.urls())
        async def it_raises_a_value_error_if_no_domain_is_given(
            self, limiter: limiters.PerDomainRateLimiter, url: str
        ):
            with pytest.raises(errors.InvalidConfigurationError):
                await limiter.limit(url)

        class DescribeAddDomain:
            domain: ClassVar[str] = "example"

            def it_adds_a_domain_to_the_limiter_using_the_default(
                self, limiter_with_default: limiters.PerDomainRateLimiter
            ):
                limiter_with_default.add_domain(self.domain)
                assert self.domain in list(
                    limiter_with_default.domain_to_limiter.keys()
                )
                assert (
                    limiter_with_default.domain_to_limiter[self.domain]
                    == limiter_with_default.default_limiter
                )

            def it_adds_a_domain_to_the_limiter_using_the_given_limiter(
                self, limiter: limiters.PerDomainRateLimiter
            ):
                limiter.add_domain(self.domain, limiters.StaticRateLimiter(0.5))
                assert self.domain in list(limiter.domain_to_limiter.keys())
                assert isinstance(
                    limiter.domain_to_limiter[self.domain], limiters.StaticRateLimiter
                )

            def it_raises_an_error_if_no_limiter_is_given_and_no_default_is_set(
                self, limiter: limiters.PerDomainRateLimiter
            ):
                with pytest.raises(errors.InvalidConfigurationError):
                    limiter.add_domain(self.domain)

    class CaseWithDomain:
        domain: ClassVar[str] = "example"
        url: ClassVar[str] = f"https://{domain}.com"

        @pytest.fixture()
        def limiter(self, mocker: MockerFixture):
            limiter = limiters.PerDomainRateLimiter()
            limiter.add_domain(self.domain, mocker.MagicMock(limiters.RateLimiter))
            return limiter

        @pytest.fixture()
        def limiter_with_default(self, mocker: MockerFixture):
            limiter = limiters.PerDomainRateLimiter(
                mocker.MagicMock(limiters.RateLimiter)
            )
            limiter.add_domain(self.domain)
            return limiter

        async def it_uses_the_default_limiter_if_no_limiter_is_given(
            self, limiter_with_default: limiters.PerDomainRateLimiter
        ):
            await limiter_with_default.limit(self.url)
            mock: Union[MockType, None] = getattr(
                limiter_with_default.default_limiter, "limit", None
            )
            assert mock is not None
            mock.assert_called_once()

        async def it_uses_the_given_limiter(
            self, limiter: limiters.PerDomainRateLimiter
        ):
            await limiter.limit(self.url)
            mock: Union[MockType, None] = getattr(
                limiter.domain_to_limiter[self.domain], "limit", None
            )
            assert mock is not None
            mock.assert_called_once()

        async def it_raises_an_error_if_no_limiter_is_found(
            self, limiter: limiters.PerDomainRateLimiter
        ):
            with pytest.raises(errors.InvalidConfigurationError):
                await limiter.limit("https://unknown.com")

    class DescribeExtractDomain:
        @pytest.fixture()
        def limiter(self):
            return limiters.PerDomainRateLimiter()

        @pytest.mark.parametrize(
            ("url", "expected"),
            [
                ("https://example.com", "example"),
                ("https://sub.example.com", "example"),
            ],
        )
        def it_extracts_the_domain_from_the_url(
            self, limiter: limiters.PerDomainRateLimiter, url: str, expected: str
        ):
            assert limiter.extract_domain(url) == expected
