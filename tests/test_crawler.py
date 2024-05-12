from typing import List, cast

import pytest
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture, MockType

from naja import crawler, events, filters, limiters, options, parsers


def _add_robot_txt_response(httpx_mock: HTTPXMock, url: str, content: str) -> None:
    httpx_mock.add_response(
        method="GET",
        url=url,
        status_code=200,
        text=content,
    )


def _add_responses(httpx_mock: HTTPXMock, urls: List[str]) -> None:
    httpx_mock.add_response(
        method="GET",
        url=urls[0],
        status_code=200,
        html="""<a href="/1">1</a>""",
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{urls[0]}/1",
        status_code=200,
        html="""<a href="/2">2</a>""",
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{urls[0]}/2",
        status_code=200,
        html="""<a href="/3">3</a>""",
    )


@pytest.mark.usefixtures("event_loop")
class DescribeCrawler:
    @pytest.fixture(scope="class")
    def initial_urls(self) -> List[str]:
        return ["https://example.com"]

    @pytest.fixture()
    def crawler(self, initial_urls: List[str]) -> crawler.Crawler:
        return crawler.Crawler(initial_urls)

    class DescribeFilter:
        def it_should_add_filter_from_callable(self, crawler: crawler.Crawler):
            assert crawler.filter(lambda url: url.raw.startswith("https"))

        def it_should_add_filter_from_kwarg(self, crawler: crawler.Crawler):
            assert crawler.filter(domain__contains="example")

        @pytest.mark.parametrize(
            "filter_instance",
            [
                filters.In("domain", ["example"]),
                filters.Contains("domain", "example"),
            ],
        )
        def it_should_add_filter_from_filter_instance(
            self, crawler: crawler.Crawler, filter_instance: filters.Filter
        ):
            assert crawler.filter(filter_instance)

        async def it_filters_out_url(
            self,
            crawler: crawler.Crawler,
            initial_urls: List[str],
            httpx_mock: HTTPXMock,
        ):
            httpx_mock.add_response(
                method="GET",
                url=f"{initial_urls[0]}/robots.txt",
                status_code=200,
                html="""
                Allow: *
                """,
            )
            httpx_mock.add_response(
                method="GET",
                url=initial_urls[0],
                status_code=200,
                html="""<a href="https://example.com/1">1</a>""",
            )
            crawler.filter(lambda url: not url.raw.endswith("/1"))
            initial_len = len(crawler.urls_seen)
            await crawler.run()
            assert len(crawler.urls_seen) == initial_len + len(initial_urls)

    class DescribeParseSiteMap:
        async def it_should_parse_sitemap_from_a_given_url(
            self,
            crawler: crawler.Crawler,
            initial_urls: List[str],
            httpx_mock: HTTPXMock,
        ):
            httpx_mock.add_response(
                method="GET",
                headers={
                    "Content-Type": "text/xml",
                },
                url=f"{initial_urls[0]}/sitemap.xml",
                status_code=200,
                text=f"""<?xml version="1.0" encoding="UTF-8"?>
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                    <url>
                        <loc>{initial_urls[0]}/1</loc>
                    </url>
                </urlset>
                """,
            )
            found_links = await crawler.parse_site_map(f"{initial_urls[0]}/sitemap.xml")
            assert httpx_mock.get_request(
                method="GET", url=f"{initial_urls[0]}/sitemap.xml"
            )
            assert len(found_links) == 1

    class DescribeRun:
        @pytest.fixture()
        def assert_all_responses_were_requested(self) -> bool:
            return False

        async def it_should_crawl_urls(
            self,
            crawler: crawler.Crawler,
            initial_urls: List[str],
            httpx_mock: HTTPXMock,
        ):
            _add_robot_txt_response(
                httpx_mock, f"{initial_urls[0]}/robots.txt", "User-agent: *\nAllow: /"
            )
            _add_responses(httpx_mock, initial_urls)
            await crawler.run()
            assert len(crawler.urls_seen) == len(initial_urls) + 3

        async def it_should_not_crawl_urls_if_not_allowed(
            self,
            crawler: crawler.Crawler,
            initial_urls: List[str],
            httpx_mock: HTTPXMock,
        ):
            _add_robot_txt_response(
                httpx_mock,
                f"{initial_urls[0]}/robots.txt",
                "User-Agent: *\nDisallow: /\n",
            )
            _add_responses(httpx_mock, initial_urls)
            await crawler.run()
            assert len(crawler.urls_seen) == len(initial_urls)

        async def it_should_not_crawl_urls_if_not_allowed_by_user_agent(
            self,
            crawler: crawler.Crawler,
            initial_urls: List[str],
            httpx_mock: HTTPXMock,
        ):
            _add_robot_txt_response(
                httpx_mock,
                f"{initial_urls[0]}/robots.txt",
                f"User-agent: {crawler.agent}\nDisallow: /",
            )
            _add_responses(httpx_mock, initial_urls)
            await crawler.run()
            assert len(crawler.urls_seen) == len(initial_urls)

        async def it_should_limit_the_number_of_requests_for_a_domain(
            self,
            crawler: crawler.Crawler,
            initial_urls: List[str],
            httpx_mock: HTTPXMock,
            mocker: MockerFixture,
        ):
            _add_robot_txt_response(
                httpx_mock, f"{initial_urls[0]}/robots.txt", "User-agent: *\nAllow: /"
            )
            _add_responses(httpx_mock, initial_urls)
            limiter_mock = mocker.MagicMock(limiters.RateLimiter)
            crawler.options = {**crawler.options, "rate_limiter": limiter_mock}  # type: ignore  # noqa: PGH003
            await crawler.run()
            limit = cast(MockType, crawler.options["rate_limiter"].limit)
            assert initial_urls[0] in limit.mock_calls[0].args

        class DescribeOn:
            @pytest.fixture(autouse=True)
            def _add_robot_txt(
                self, initial_urls: List[str], httpx_mock: HTTPXMock
            ) -> None:
                _add_robot_txt_response(
                    httpx_mock,
                    f"{initial_urls[0]}/robots.txt",
                    "User-agent: *\nAllow: /",
                )

            async def it_should_call_on_url_found(
                self,
                crawler: crawler.Crawler,
                mocker: MockerFixture,
                initial_urls: List[str],
            ):
                mock = mocker.Mock()
                await crawler.on(events.Event.URL_FOUND, mock).run()
                mock.assert_called_once_with(
                    parsers.parse_url(initial_urls[0]), crawler=crawler
                )

            async def it_should_call_on_error(
                self,
                crawler: crawler.Crawler,
                mocker: MockerFixture,
                initial_urls: List[str],
                httpx_mock: HTTPXMock,
            ):
                httpx_mock.add_response(
                    method="GET",
                    url=initial_urls[0],
                    status_code=500,
                    text="Internal Server Error",
                )
                mock = mocker.Mock()
                await crawler.on(events.Event.ERROR, mock).run()
                mock.assert_called_once()
                assert isinstance(mock.call_args[0][0], Exception)
                assert mock.mock_calls[0].kwargs["crawler"] is crawler

        class DescribeRetry:
            @pytest.fixture(autouse=True)
            def _add_robot_txt(
                self, initial_urls: List[str], httpx_mock: HTTPXMock
            ) -> None:
                _add_robot_txt_response(
                    httpx_mock,
                    f"{initial_urls[0]}/robots.txt",
                    "User-agent: *\nAllow: /",
                )

            class CaseMustRetryForStatusCodesPassedAsOption:
                @pytest.fixture()
                def assert_all_responses_were_requested(self) -> bool:
                    return True

                @pytest.fixture(params=[[500, 502, 503, 504]])
                def crawler_with_retry_option(
                    self, request: pytest.FixtureRequest, initial_urls: List[str]
                ) -> crawler.Crawler:
                    return crawler.Crawler(
                        initial_urls,
                        options={"retry_for_status_codes": request.param},
                    )

                async def it_should_retry_failed_requests(
                    self,
                    crawler_with_retry_option: crawler.Crawler,
                    initial_urls: List[str],
                    httpx_mock: HTTPXMock,
                ):
                    content = b""
                    httpx_mock.add_response(
                        method="GET",
                        url=initial_urls[0],
                        status_code=500,
                        content=b"Internal Server Error",
                    )
                    httpx_mock.add_response(
                        method="GET",
                        url=initial_urls[0],
                        status_code=200,
                        content=content,
                    )
                    await crawler_with_retry_option.run()

            class CaseRetryHandlerSet:
                @pytest.fixture()
                def assert_all_responses_were_requested(self) -> bool:
                    return True

                @pytest.mark.parametrize(
                    "retry_handler",
                    [
                        lambda url, response, crawler: url.raw  # noqa: ARG005
                        == "https://example.com",
                        lambda url, response, crawler: response.status_code  # noqa: ARG005
                        == 500,  # noqa: PLR2004
                    ],
                )
                async def it_should_retry_based_on_handler_return_value(
                    self,
                    crawler: crawler.Crawler,
                    retry_handler: options.RetryHandler,
                    initial_urls: List[str],
                    httpx_mock: HTTPXMock,
                ):
                    httpx_mock.add_response(
                        method="GET",
                        url=initial_urls[0],
                        status_code=500,
                        content=b"Internal Server Error",
                    )
                    httpx_mock.add_response(
                        method="GET",
                        url=initial_urls[0],
                        status_code=200,
                        content=b"",
                    )
                    await crawler.retry(retry_handler).run()
