import asyncio
from typing import Callable, Generator, Iterable

import httpx

from . import filters, limiters, parsers
from .protocols import Filterer, Parser, RateLimiter

FoundUrlsHandler = Callable[[set[str]], Generator[set[str], None, None]]

ParserFactory = Callable[[str, Filterer], Parser]


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
    ) -> None:
        self.client = client

        self.todo: asyncio.Queue[asyncio.Task] = asyncio.Queue()

        self.start_urls = set(urls)
        self.urls_seen: set[str] = set()
        self.done: set[str] = set()
        self._found_urls_handlers = set(found_urls_handlers)

        self.parser_class = parser_class or parsers.UrlParser
        self.filter_url = filterer or filters.UrlFilterer()

        self.rate_limiter = rate_limiter or limiters.NoLimitRateLimiter()

        self.num_workers = workers
        self.limit = limit
        self.total_pages = 0

    async def run(self) -> None:
        """
        Run the crawler.
        """
        await self.on_found_links(self.start_urls)

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

    async def parse_links(self, base: str, text: str) -> set[str]:
        parser = self.parser_class(base, self.filter_url)
        parser.parse(text)
        return parser.found_links

    async def on_found_links(self, urls: set[str]) -> None:
        new = urls - self.urls_seen
        self.urls_seen.update(new)

        if len(self._found_urls_handlers) > 0:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(handler(new) for handler in self._found_urls_handlers)

        for url in new:
            await self.put_todo(url)

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

    filterer = filters.UrlFilterer(
        allowed_domains={"mcoding.io"},
        allowed_schemes={"https", "http"},
        allowed_filetypes={".html", ".php", ""},
    )

    start = time.perf_counter()
    async with httpx.AsyncClient() as client:
        crawler = Crawler(
            client=client, urls=["https://mcoding.io"], filterer=filterer, workers=5
        )
        await crawler.run()
    end = time.perf_counter()

    seen = sorted(crawler.urls_seen)
    print("Results:")
    for url in seen:
        print(url)
    print(f"Crawled: {len(crawler.done)} URLs")
    print(f"Found: {len(seen)} URLs")
    print(f"Time: {end - start} seconds")


if __name__ == "__main__":
    asyncio.run(main())


