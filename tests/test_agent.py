import pytest

from naja import agent


class DescribeUserAgent:
    @pytest.fixture()
    def user_agent(self) -> agent.UserAgent:
        return agent.UserAgent("test")

    def it_should_add_parser_for_domain(self, user_agent: agent.UserAgent):
        user_agent.respect("example", "User-agent: *\nAllow: /")
        assert "example" in user_agent.acknowledged_domains

    class DescribeCanAccess:
        def it_should_return_true_if_allowed(self, user_agent: agent.UserAgent):
            user_agent.respect("example", "User-agent: *\nAllow: /")
            assert user_agent.can_access("example", "https://example.com")

        def it_should_return_false_if_not_allowed(self, user_agent: agent.UserAgent):
            user_agent.respect("example", "User-agent: *\nDisallow: /")
            assert not user_agent.can_access("example", "https://example.com")

    class DescribeCrawlDelay:
        def it_should_return_crawl_delay(self, user_agent: agent.UserAgent):
            user_agent.respect("example", "User-agent: *\nCrawl-delay: 1")
            crawl_delay = user_agent.get_crawl_delay("example")
            assert crawl_delay == "1"

        def it_should_return_none_if_not_acknowledged(
            self, user_agent: agent.UserAgent
        ):
            assert user_agent.get_crawl_delay("example") is None

    @pytest.mark.skip(reason="Bug on robot file parser.")
    class DescribeRequestRate:
        @pytest.mark.parametrize(
            ("robots_txt", "expected"),
            [
                ("User-agent: *\nRequest-rate: 1/10s", (1, 10)),
                ("User-agent: *\nRequest-rate: 2/10s", (2, 10)),
                ("User-agent: *\nRequest-rate: 1/5s", (1, 5)),
            ],
        )
        def it_should_return_request_rate(
            self,
            user_agent: agent.UserAgent,
            robots_txt: str,
            expected: tuple[int, int],
        ):
            user_agent.respect("example", robots_txt)
            request_rate = user_agent.get_request_rate("example")
            assert request_rate is not None
            assert (request_rate.requests, request_rate.seconds) == expected

        def it_should_return_none_if_not_acknowledged(
            self, user_agent: agent.UserAgent
        ):
            assert user_agent.get_request_rate("example") is None

    class DescribeGetSiteMaps:
        def it_should_return_sitemap(self, user_agent: agent.UserAgent):
            site_map_path = "/sitemap.xml"
            user_agent.respect("example", "Sitemap: /sitemap.xml")
            site_maps = user_agent.get_site_maps("example")
            assert site_maps is not None
            assert site_map_path in site_maps

        def it_should_return_none_if_not_acknowledged(
            self, user_agent: agent.UserAgent
        ):
            assert user_agent.get_site_maps("example") is None
