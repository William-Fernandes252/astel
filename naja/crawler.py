from __future__ import annotations

import asyncio
import asyncio.constants
from typing import Callable, Coroutine, Iterable, Type

from naja import agent
from naja.options import CrawlerOptions, merge_with_default_options

from . import parsers

FoundUrlsHandler = Callable[[set], Coroutine[set, None, None]]

ParserFactory = Type[parsers.Parser]


class Crawler:
    """A simple asyncronous web crawler that uses httpx to navigate to websites

    Args:
        client (httpx.AsyncClient): An instance of `httpx.AsyncClient` to use for
        network requests.
        urls (Iterable[str]): An iterable of URLs to start the crawling with.
        workers (int, optional): The number of worker tasks to run in parallel.
        Defaults to 10.
        limit (int, optional): The maximum number of pages to crawl. Defaults to 25.
        found_urls_handlers (Iterable[FoundUrlsHandler], optional): A list of
        FoundUrlsHandler objects to use for processing
        newly found URLs. Defaults to [].
        parser_class (ParserFactory | None, optional): A parser factory object to use
        for parsing HTML responses.
        Defaults to `type(parsers.UrlParser)`. Defaults to None.
        rate_limiter (limiters.RateLimiter | None, optional): A rate limiter to limit
        the number of requests sent per second.
        Defaults to `limiters.NoLimitRateLimiter`. Defaults to None.
    """

    def __init__(
        self, urls: Iterable[str], options: CrawlerOptions | None = None
    ) -> None:
        options = merge_with_default_options(options)

        self.todo: asyncio.Queue[asyncio.Task] = asyncio.Queue()
        self.client = options["client"]
        self.start_urls = set(urls)
        self.urls_seen: set[parsers.Url] = set()
        self.done: set[str] = set()
        self.parser_class = options["parser_class"]
        self.agent = agent.UserAgent(options["user_agent"])
        self.rate_limiter = options["rate_limiter"]
        self.num_workers = options["workers"]
        self.limit = options["limit"]
        self.total_pages = 0

    async def run(self) -> None:
        """
        Run the crawler.
        """
        await self._on_found_links({parsers.parse_url(url) for url in self.start_urls})

        workers = [asyncio.create_task(self._worker()) for _ in range(self.num_workers)]
        await self.todo.join()

        for worker in workers:
            worker.cancel()

    async def _worker(self) -> None:
        while True:
            try:
                await self._process_one()
            except asyncio.CancelledError:
                return

    async def _process_one(self) -> None:
        task = await self.todo.get()
        await task
        self.todo.task_done()

    async def _crawl(self, url: str) -> None:
        await self.rate_limiter.limit(url)  # type: ignore[call-arg]

        response = await self.client.get(url, follow_redirects=True)

        found_links = await self._parse_links(
            base=str(response.url),
            text=response.text,
        )

        await self._on_found_links(found_links)

        self.done.add(url)

    async def _parse_links(self, base: str, text: str) -> set[parsers.Url]:
        parser = self.parser_class(base=base)
        parser.feed(text)
        return parser.found_links

    async def _acknowledge_domains(
        self, parsed_urls: set[parsers.Url]
    ) -> set[parsers.Url]:
        new = parsed_urls - self.urls_seen
        for result in new:
            self.agent.respect(
                result.domain, f"{result.scheme}://{result.domain}/robots.txt"
            )

            tasks = [
                asyncio.create_task(
                    self._acknowledge_domains(await self.parse_site_map(site_map_path))
                )
                for site_map_path in self.agent.get_site_maps(result.domain) or []
            ]
            await asyncio.wait(tasks)

            self.rate_limiter.configure(  # type: ignore[call-arg]
                domain=result.domain,
                crawl_delay=self.agent.get_crawl_delay(result.domain),
                request_rate=self.agent.get_request_rate(result.domain),
            )

        self.urls_seen.update(new)

        return new

    async def parse_site_map(self, site_map_path: str) -> set[parsers.Url]:
        parser = parsers.SiteMapParser(site_map_path)
        response = await self.client.get(site_map_path)
        parser.feed(response.text)
        return parser.found_links

    async def _on_found_links(self, urls: set[parsers.Url]) -> None:
        for result in await self._acknowledge_domains(urls):
            await self._put_todo(result.raw)

    async def _put_todo(self, url: str) -> None:
        if self.total_pages > self.limit:
            return
        self.total_pages += 1
        await self.todo.put(asyncio.create_task(self._crawl(url)))


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
