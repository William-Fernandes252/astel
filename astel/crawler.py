"""Crawler module.

This module defines the `Crawler` class that can be used to crawl websites asynchronously.
"""  # noqa: E501

from __future__ import annotations

import asyncio
import asyncio.constants
from typing import Iterable, List, Optional, Set, Union, cast

import httpx
from typing_extensions import Self  # type: ignore[attr-defined]

from astel import agent, events, filters, limiters, parsers
from astel.options import (
    CrawlerOptions,
    ParserFactory,
    RetryHandler,
    merge_with_default_options,
)


class Crawler:
    """An asynchronous web crawler that can be used to extract, process and follow links in webpages.

    Args:
        urls (Iterable[str]): The URLs to start the crawler with.
        options (CrawlerOptions, optional): The options to use for the crawler.
    """  # noqa: E501

    _todo: asyncio.Queue[asyncio.Task]
    _client: httpx.AsyncClient
    _start_urls: Set[str]
    _urls_seen: Set[parsers.Url]
    _done: Set[str]
    _parser_factory: ParserFactory
    _agent: agent.UserAgent
    _rate_limiter: limiters.RateLimiter
    _num_workers: int
    _limit: int
    _total_pages: int
    _filters: List[filters.CallableFilter]
    _event_emitter: events.EventEmitter
    _workers: List[asyncio.Task]
    _options: CrawlerOptions
    _must_retry: RetryHandler | None

    def __init__(
        self, urls: Iterable[str], options: CrawlerOptions | None = None
    ) -> None:
        self._todo: asyncio.Queue[asyncio.Task] = asyncio.Queue()
        self._start_urls = set(urls)
        self._urls_seen: set[parsers.Url] = set()
        self._done: set[str] = set()
        self._filters: List[filters.Filter] = []
        self._options = merge_with_default_options(options)
        self._client = self._options["client"]
        self._parser_factory = self._options["parser_factory"]
        self._agent = agent.UserAgent(self._options["user_agent"])
        self._rate_limiter = self._options["rate_limiter"]
        self._num_workers = self._options["workers"]
        self._limit = self._options["limit"]
        self._total_pages = 0
        self._event_emitter = self._options["event_emitter_factory"]()

        def _must_retry(
            url: parsers.Url, response: Union[httpx.Response, None], _: Crawler
        ) -> bool:
            return bool(
                (
                    response
                    and response.status_code in self._options["retry_for_status_codes"]
                )
                and url
            )

        self._must_retry = (
            cast(RetryHandler, _must_retry)
            if self._options["retry_for_status_codes"]
            else None
        )

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
        try:
            await task
        except httpx.HTTPError as e:
            self._emit_event(events.Event.ERROR, e)
            if self._must_retry and self._must_retry(
                parsers.parse_url(str(e.request.url)),
                getattr(e, "response", None),
                self,
            ):
                await self._put_todo(parsers.parse_url(str(e.request.url)))
        finally:
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
        return (
            await self._client.send(request, follow_redirects=True)
        ).raise_for_status()

    async def _parse_links(self, base: str, text: str) -> set[parsers.Url]:
        parser = self._parser_factory(base=base)
        parser.feed(text)
        return {link for link in parser.found_links if self._apply_filters(link)}

    def _apply_filters(self, url: parsers.Url) -> bool:
        return all(f(url) for f in self._filters)

    async def _acknowledge_domains(
        self, parsed_urls: set[parsers.Url]
    ) -> set[parsers.Url]:
        new = parsed_urls - self._urls_seen
        for result in new:
            robots_txt = (
                (
                    await self._client.get(
                        f"{result.scheme}://{result.domain}/robots.txt",
                        timeout=5,
                        follow_redirects=False,
                        headers={
                            "User-Agent": self._agent.name,
                            "Accept": "text/plain",
                        },
                    )
                )
                .raise_for_status()
                .text
            )
            self._agent.respect(result.domain, robots_txt)

            tasks = [
                asyncio.create_task(
                    self._acknowledge_domains(await self.parse_site_map(site_map_path))
                )
                for site_map_path in self._agent.get_site_maps(result.domain) or []
            ]
            if len(tasks) > 0:
                done, _ = await asyncio.wait(tasks)
                for future in done:
                    task_result = future.result()
                    if isinstance(task_result, set):
                        new.update(future.result())
                    else:
                        raise cast(BaseException, task_result)

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
        response = (await self._client.get(site_map_path)).raise_for_status()
        parser.feed(response.text)
        return parser.found_links

    def filter(self, *args: filters.CallableFilter, **kwargs) -> Self:
        """Add URL filters to the crawler.

        Filters can be used to determine which URLs should be ignored.

        Args:
            *args (Filter): A list of `Filter` objects to add to the crawler.
            **kwargs (Any): A list of keyword arguments to create `Filter` objects from.

        Returns:
            Crawler: The `Crawler` object with the added filters.

        Raises:
            ValueError: If a filter could not be created from the given keyword arguments.

        Examples:
            >>> crawler.filter(filters.StartsWith("scheme", "http"))
            >>> crawler.filter(filters.Matches("https://example.com"))
            >>> crawler.filter(domain__in=["example.com"])
        """  # noqa: E501
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

    def on(self, event: events.Event, handler: events.Handler) -> Self:
        """Add an event handler to the crawler.

        An event is emitted when
        - a request is ready to be sent (`Event.REQUEST`): the `httpx.Request` object is
        passed to the handler.
        - a response is received (`Event.RESPONSE`): the `httpx.Response` object is
        passed to the handler.
        - an error occurs (`Event.ERROR`): the `Error` object is passed to the handler.
        - a URL is done being processed (`Event.DONE`): the `astel.parsers.Url` object
        is passed to the handler.
        - a URL is found in a page (`Event.URL_FOUND`): the `astel.parsers.Url` object is passed to the handler.

        Args:
            event (str): The event to add the handler to.
            handler (Callable): The handler to add to the event.
        """  # noqa: E501
        self._event_emitter.on(event, handler)
        return self

    def _emit_event(self, event: events.Event, *data) -> None:
        self._event_emitter.emit(event, *data, crawler=self)

    def stop(self, *, reset: bool = False) -> None:
        """Stop the crawler current execution.

        Args:
            reset (bool, optional: Optionally, reset the crawler on the same call. Defaults to `False`.
        """  # noqa: E501
        for worker in self._workers:
            worker.cancel()
        if reset:
            self.reset()

    def reset(self) -> None:
        """Reset the crawler."""
        self._done.clear()
        self._urls_seen.clear()
        self._total_pages = 0

    def retry(self, handler: RetryHandler) -> Self:
        """Set a handler to determine whether a request should be retried.

        Args:
            handler (Callable): A function that takes a `httpx.Response` and a `astel.parsers.Url` object and returns a boolean indicating whether the request should be retried.

        Returns:
            Crawler: The `Crawler` object with the retry handler set.
        """  # noqa: E501
        self._must_retry = handler
        return self

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
    def parser_factory(self) -> ParserFactory:
        """The parser factory object used by the crawler to parse HTML responses."""
        return self._parser_factory

    @property
    def start_urls(self) -> Set[str]:
        """The URLs that the crawler was started with."""
        return self._start_urls

    @property
    def agent(self) -> str:
        """The user agent used by the crawler."""
        return self._agent.name

    @property
    def options(self) -> CrawlerOptions:
        """The options used by the crawler."""
        return self._options

    @options.setter
    def options(self, options: Optional[CrawlerOptions] = None) -> None:
        """Set the options used by the crawler."""
        self._options = merge_with_default_options(options)
        self._client = self._options["client"]
        self._agent = agent.UserAgent(self._options["user_agent"])
        self._rate_limiter = self._options["rate_limiter"]
        self._num_workers = self._options["workers"]
        self._limit = self._options["limit"]
        self._parser_factory = self._options["parser_factory"]
        self._event_emitter = self._options["event_emitter_factory"]()
