from __future__ import annotations

import asyncio
import asyncio.constants
from typing import TYPE_CHECKING, Callable, Coroutine, Iterable, List, Set, Type

import httpx
from typing_extensions import Self

from naja import agent, events, filters, limiters, parsers
from naja.options import CrawlerOptions, merge_with_default_options

if TYPE_CHECKING:
    from eventemitter import EventEmitter

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

    _todo: asyncio.Queue[asyncio.Task]
    _client: httpx.AsyncClient
    _start_urls: Set[str]
    _urls_seen: Set[parsers.Url]
    _done: Set[str]
    _parser_class: Type[parsers.Parser]
    _agent: agent.UserAgent
    _rate_limiter: limiters.RateLimiter
    _num_workers: int
    _limit: int
    _total_pages: int
    _filters: List[filters.CallableFilter]
    _event_emitter: EventEmitter
    _workers: List[asyncio.Task]
    _options: CrawlerOptions

    def __init__(
        self, urls: Iterable[str], options: CrawlerOptions | None = None
    ) -> None:
        self._options = merge_with_default_options(options)
        self._todo: asyncio.Queue[asyncio.Task] = asyncio.Queue()
        self._client = self._options["client"]
        self._start_urls = set(urls)
        self._urls_seen: set[parsers.Url] = set()
        self._done: set[str] = set()
        self._parser_class = self._options["parser_class"]
        self._agent = agent.UserAgent(self._options["user_agent"])
        self._rate_limiter = self._options["rate_limiter"]
        self._num_workers = self._options["workers"]
        self._limit = self._options["limit"]
        self._total_pages = 0
        self._filters: List[filters.Filter] = []
        self._event_emitter = self._options["event_emitter"]

    async def run(self) -> None:
        """Run the crawler."""
        await self._on_found_links({parsers.parse_url(url) for url in self._start_urls})

        self._workers = [
            asyncio.create_task(self._worker()) for _ in range(self._num_workers)
        ]
        await self._todo.join()

        for worker in self._workers:
            worker.cancel()

    async def _worker(self) -> None:
        while True:
            try:
                await self._process_one()
            except asyncio.CancelledError:
                return

    async def _process_one(self) -> None:
        task = await self._todo.get()
        await task
        self._todo.task_done()

    async def _crawl(self, url: parsers.Url) -> None:
        await self._rate_limiter.limit(url.raw)

        if self._agent.can_access(url.domain, url.raw):
            response = await self._send_request(url)
            self._emit_event(events.Event.RESPONSE, response)

            await self._on_found_links(
                await self._parse_links(
                    base=str(response.url),
                    text=response.text,
                )
            )

        self._done.add(url.raw)
        self._emit_event(events.Event.DONE, url)

    async def _send_request(self, url: parsers.Url) -> httpx.Response:
        request = httpx.Request(
            "GET", url.raw, headers={"User-Agent": self._agent.name}
        )
        self._emit_event(events.Event.REQUEST, request)
        return await self._client.send(request, follow_redirects=True)

    async def _parse_links(self, base: str, text: str) -> set[parsers.Url]:
        parser = self._parser_class(base=base)
        parser.feed(text)
        return {link for link in parser.found_links if self._apply_filters(link)}

    def _apply_filters(self, url: parsers.Url) -> bool:
        return all(f(url) for f in self._filters)

    async def _acknowledge_domains(
        self, parsed_urls: set[parsers.Url]
    ) -> set[parsers.Url]:
        new = parsed_urls - self._urls_seen
        for result in new:
            self._agent.respect(
                result.domain, f"{result.scheme}://{result.domain}/robots.txt"
            )

            tasks = [
                asyncio.create_task(
                    self._acknowledge_domains(await self.parse_site_map(site_map_path))
                )
                for site_map_path in self._agent.get_site_maps(result.domain) or []
            ]
            await asyncio.wait(tasks)

            self._rate_limiter.configure(
                {
                    "domain": result.domain,
                    "crawl_delay": self._agent.get_crawl_delay(result.domain),
                    "request_rate": self._agent.get_request_rate(result.domain),
                }
            )

        self._urls_seen.update(new)

        return new

    async def parse_site_map(self, site_map_path: str) -> Set[parsers.Url]:
        """Parse a sitemap.xml file and return the URLs found in it.

        Args:
            site_map_path (str): The URL of the sitemap.xml file.

        Returns:
            Set[parsers.Url]: The URLs found in the sitemap.xml file.
        """
        parser = parsers.SiteMapParser(site_map_path)
        response = await self._client.get(site_map_path)
        parser.feed(response.text)
        return parser.found_links

    def filter(self, *args: filters.CallableFilter, **kwargs) -> Self:
        """Add URL filters to the crawler.

        Filters can be used to determine which URLs should be ignored by the Crawler.

        Args:
            *args (Filter): A list of Filter objects to add to the crawler.
            **kwargs: A list of keyword arguments to create Filter objects from.

        Returns:
            Crawler: The Crawler object with the added filters.

        Raises:
            ValueError: If a filter could not be created from the given keyword
            arguments.

        Examples:
            >>> crawler.filter(filters.StartsWith("scheme", "http"))
            >>> crawler.filter(filters.Matches("https://example.com"))
            >>> crawler.filter(domain__in=["example.com"])
        """
        self._filters.extend(
            [
                *args,
                *[
                    f
                    for f in (
                        filters.create_from_kwarg(key, value)
                        for key, value in kwargs.items()
                    )
                    if f is not None
                ],
            ],
        )
        return self

    async def _on_found_links(self, urls: set[parsers.Url]) -> None:
        for url in urls:
            self._emit_event(events.Event.URL_FOUND, url)
        for url in await self._acknowledge_domains(urls):
            await self._put_todo(url)

    async def _put_todo(self, url: parsers.Url) -> None:
        if self._total_pages > self._limit:
            return
        self._total_pages += 1
        await self._todo.put(asyncio.create_task(self._crawl(url)))

    def on(self, event: events.Event, handler: events.Handler) -> None:
        """Add an event handler to the crawler.

        An event is emitted when
        - a request is ready to be sent (`Event.REQUEST`): the `httpx.Request` object is
        passed to the handler.
        - a response is received (`Event.RESPONSE`): the `httpx.Response` object is
        passed to the handler.
        - an error occurs (`Event.ERROR`): the `Error` object is passed to the handler.
        - a URL is done being processed (`Event.DONE`): the `naja.parsers.Url` object
        is passed to the handler.
        - a URL is found in a page (`Event.URL_FOUND`): the `naja.parsers.Url` object is
        passed to the handler.

        Args:
            event (str): The event to add the handler to.
            handler (Callable): The handler to add to the event.
        """
        self._event_emitter.on(event, handler)

    def _emit_event(self, *args, **kwargs) -> None:
        self._event_emitter.emit(*args, **kwargs, crawler=self)

    def stop(self, *, reset: bool = False) -> None:
        """Stop the crawler current execution.

        Args:
            reset (bool, optional: Optionally, reset the crawler on the same call.
            Defaults to False.
        """
        for worker in self._workers:
            worker.cancel()
        if reset:
            self.reset()

    def reset(self) -> None:
        """Reset the crawler."""
        self._done.clear()
        self._urls_seen.clear()
        self._total_pages = 0

    @property
    def total_pages(self) -> int:
        """The total number of pages queued by the crawler."""
        return self._total_pages

    @property
    def done(self) -> set[str]:
        """The URLs that have been crawled by the crawler."""
        return self._done

    @property
    def urls_seen(self) -> set[parsers.Url]:
        """The URLs that have been seen by the crawler."""
        return self._urls_seen

    @property
    def rate_limiter(self) -> limiters.RateLimiter:
        """The rate limiter used by the crawler."""
        return self._rate_limiter

    @property
    def num_workers(self) -> int:
        """The number of worker tasks used by the crawler."""
        return self._num_workers

    @property
    def limit(self) -> int:
        """The maximum number of pages to crawl.

        It is used as a fail-safe to prevent the crawler from running indefinitely.
        """
        return self._limit

    @property
    def parser_class(self) -> Type[parsers.Parser]:
        """The parser factory object used by the crawler to parse HTML responses."""
        return self._parser_class

    @property
    def start_urls(self) -> Set[str]:
        """The URLs that the crawler was started with."""
        return self._start_urls

    @property
    def options(self) -> CrawlerOptions:
        """The options used by the crawler."""
        return self._options

    @options.setter
    def options(self, options: CrawlerOptions) -> None:
        """Set the options used by the crawler."""
        self._options = merge_with_default_options(options)
        self._client = self._options["client"]
        self._agent = agent.UserAgent(self._options["user_agent"])
        self._rate_limiter = self._options["rate_limiter"]
        self._num_workers = self._options["workers"]
        self._limit = self._options["limit"]
        self._parser_class = self._options["parser_class"]
        self._event_emitter = self._options["event_emitter"]
