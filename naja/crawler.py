from __future__ import annotations

import asyncio
from typing import Callable, Generator, Iterable, Set, Type

import httpx

from . import agent, limiters, parsers
from .filterers import UrlFilterer
from .protocols import Filterer, Parser, RateLimiter, Url

FoundUrlsHandler = Callable[[Set[str]], Generator[Set[str], None, None]]

ParserFactory = Type[Parser]


class Crawler:
    """
    A simple asyncronous web crawler that uses httpx to navigate to websites
    asynchronously and do some work with its content.

    :param client: An instance of `httpx.AsyncClient` to use for network requests.
    :type client: `httpx.AsyncClient`

    :param urls: An iterable of URLs to start the crawling with.
    :type urls: `Iterable[str]`

    :param filterer: A filterer to filter out URLs to ignore.
    :type filter_url: `Filter | None`

    :param workers: The number of worker tasks to run in parallel.
    :type workers: `int`

    :param limit: The maximum number of pages to crawl.
    :type limit: `int`

    :param found_urls_handlers: A list of FoundUrlsHandler objects to use for processing
    newly found URLs.
    :type found_urls_handlers: `Iterable[FoundUrlsHandler]`

    :param parser_class: A parser factory object to use for parsing HTML responses. Defaults to `type(parsers.UrlParser)`.
    :type parser_class: `ParserFactory | None`

    :param rate_limiter: A rate limiter to limit the number of requests sent per second. Defaults to `limiters.NoLimitRateLimiter`.
    :type rate_limiter: `RateLimiter | None`

    :return: `None`
    :rtype: `None`
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        urls: Iterable[str],
        filterer: Filterer | None = None,
        workers: int = 10,
        limit: int = 25,
        found_urls_handlers: Iterable[FoundUrlsHandler] = [],
        parser_class: ParserFactory | None = None,
        rate_limiter: RateLimiter | None = None,
        user_agent: agent.UserAgent | None = None,
    ) -> None:
        self.client = client

        self.todo: asyncio.Queue[asyncio.Task] = asyncio.Queue()

        self.start_urls = set(urls)
        self.urls_seen: set[Url] = set()
        self.done: set[str] = set()
        self._found_urls_handlers = set(found_urls_handlers)
        self.agent = user_agent or agent.UserAgent("naja")

        self.parser_class = parser_class or parsers.HTMLAnchorsParser
        self.filter_url: Filterer = filterer or UrlFilterer()

        self.rate_limiter = rate_limiter or limiters.NoLimitRateLimiter()

        self.num_workers = workers
        self.limit = limit
        self.total_pages = 0

    async def run(self) -> None:
        """
        Run the crawler.
        """
        await self.on_found_links(
            {self.parser_class.parse_url(url) for url in self.start_urls}
        )

        workers = [asyncio.create_task(self.worker()) for _ in range(self.num_workers)]
        await self.todo.join()

        for worker in workers:
            worker.cancel()

    async def worker(self) -> None:
        while True:
            try:
                await self.process_one()
            except asyncio.CancelledError:
                return

    async def process_one(self) -> None:
        task = await self.todo.get()
        try:
            await task
        except Exception as exc:
            # logging and retrying
            pass
        finally:
            self.todo.task_done()

    async def crawl(self, url: str) -> None:
        await self.rate_limiter.limit(url)

        response = await self.client.get(url, follow_redirects=True)

        found_links = await self.parse_links(
            base=str(response.url),
            text=response.text,
        )

        await self.on_found_links(found_links)

        self.done.add(url)

    async def parse_links(self, base: str, text: str) -> Set[Url]:
        parser = self.parser_class(base, self.filter_url)
        parser.parse_content(text)
        return parser.found_links

    async def _acknowledge_domains(self, parsed_urls: Set[Url]) -> Set[Url]:
        new = parsed_urls - self.urls_seen
        for result in new:
            self.agent.respect(
                result.domain, f"{result.scheme}://{result.domain}/robots.txt"
            )

            async with asyncio.TaskGroup() as tg:
                for site_map_path in self.agent.get_site_maps(result.domain) or []:
                    tg.create_task(
                        self._acknowledge_domains(
                            await self.parse_site_map(site_map_path)
                        )
                    )

            self.rate_limiter.configure(
                domain=result.domain,
                crawl_delay=self.agent.get_crawl_delay(result.domain),
                request_rate=self.agent.get_request_rate(result.domain),
            )

        self.urls_seen.update(new)

        return new

    async def parse_site_map(self, site_map_path: str) -> Set[Url]:
        parser = parsers.SiteMapParser(site_map_path, self.filter_url)
        response = await self.client.get(site_map_path)
        parser.parse_content(response.text)
        return parser.found_links

    async def on_found_links(self, urls: Set[Url]) -> None:
        new = await self._acknowledge_domains(urls)

        if len(self._found_urls_handlers) > 0:
            async with asyncio.TaskGroup() as tg:
                for handler in self._found_urls_handlers:
                    tg.create_task(handler({result.raw for result in new}))

        for result in new:
            await self.put_todo(result.raw)

    async def put_todo(self, url: str) -> None:
        if self.total_pages > self.limit:
            return
        self.total_pages += 1
        await self.todo.put(asyncio.create_task(self.crawl(url)))

    def add_found_urls_handler(self, handler: FoundUrlsHandler) -> None:
        self._found_urls_handlers.add(handler)

    def remove_found_urls_handler(self, handler: FoundUrlsHandler) -> None:
        self._found_urls_handlers.discard(handler)


async def main() -> None:
    import time

    filterer = UrlFilterer(
        domain__in=("mcoding.io"),
        scheme__in=("https", "http"),
        filetype__in=(".html", ".php", ""),
    )

    start = time.perf_counter()
    async with httpx.AsyncClient() as client:
        crawler = Crawler(
            client=client, urls=["https://mcoding.io"], filterer=filterer, workers=5
        )
        await crawler.run()
    end = time.perf_counter()

    seen = crawler.urls_seen
    print("Results:")
    for result in seen:
        print(result.raw)
    print(f"Crawled: {len(crawler.done)} URLs")
    print(f"Found: {len(seen)} URLs")
    print(f"Time: {end - start} seconds")


if __name__ == "__main__":
    asyncio.run(main())


# TODO:
# - add logging
# - add retry
# - respect robots.txt *done*
# - find links in sitemap.xml *done*
# - provide a user agent *done*
# - normalize urls (e.g. https://mcoding.io/ -> https://mcoding.io) *done*
# - skip filetypes or filetypes only
# - max depth of links
# - store connections as graph
