from hypothesis import given, provisional

from astel import parsers


class DescribeParseUrl:
    @given(url=provisional.urls())
    def it_parses_a_raw_url_str_into_its_components(self, url: str):
        parsed_url = parsers.parse_url(url)
        for attr in ["scheme", "domain", "path", "params", "query", "fragment"]:
            assert hasattr(parsed_url, attr)

    def it_parses_a_raw_url_str_into_its_components_with_base(self):
        parsed_url = parsers.parse_url("https://example.com", "https://example.com")
        assert parsed_url.domain == "example.com"

    def it_parses_a_raw_url_str_into_its_components_with_base_relative_url(self):
        parsed_url = parsers.parse_url("/path", "https://example.com")
        assert parsed_url.domain == "example.com"
        assert parsed_url.path == "/path"

    def it_exposes_the_raw_url_str(self):
        parsed_url = parsers.parse_url("https://example.com")
        assert parsed_url.raw == "https://example.com"


class DescribeHTMLAnchorsParser:
    def it_extracts_urls_from_html_anchors_using_the_base(self):
        parser = parsers.HTMLAnchorsParser(base="https://example.com")
        parser.feed('<a href="/path">')
        assert parser.found_links == {parsers.parse_url("/path", "https://example.com")}

    def it_extracts_urls_from_html_anchors_without_the_base(self):
        parser = parsers.HTMLAnchorsParser()
        parser.feed('<a href="https://example.com/path">')
        assert parser.found_links == {parsers.parse_url("https://example.com/path")}


class DescribeSiteMapParser:
    def it_extracts_urls_from_a_sitemap(self):
        parser = parsers.SiteMapParser(base="https://example.com")
        parser.feed(
            """<?xml version="1.0" encoding="UTF-8"?>
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                <url>
                    <loc>https://example.com/path</loc>
                </url>
            </urlset>"""
        )
        assert parser.found_links == {parsers.parse_url("/path", "https://example.com")}
