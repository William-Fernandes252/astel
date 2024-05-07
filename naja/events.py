from enum import Enum
from typing import Protocol, Union

import httpx

from naja import errors, parsers


class Event(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    DONE = "done"
    URL_FOUND = "url_found"


class RequestHandler(Protocol):
    """Handler for requests made by a crawler."""

    def __call__(self, request: httpx.Request) -> None: ...


class ResponseHandler(Protocol):
    """Handler for responses received by a crawler."""

    def __call__(self, response: httpx.Response) -> None: ...


class ErrorHandler(Protocol):
    """Handler for errors occurred during a crawler execution."""

    def __call__(self, error: errors.Error) -> None: ...


class DoneHandler(Protocol):
    """Handler for when a crawler finishes processing a URL."""

    def __call__(self, url: parsers.Url) -> None: ...


class UrlFoundHandler(Protocol):
    """Handler for when a URL is found in a page."""

    def __call__(self, url: parsers.Url) -> None: ...


Handler = Union[
    ResponseHandler, RequestHandler, ErrorHandler, DoneHandler, UrlFoundHandler
]
