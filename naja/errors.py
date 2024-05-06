from __future__ import annotations


class Error(Exception):
    """
    Base class for exceptions in this package
    """

    default_message: str | None = None

    def __init__(self, message: str = "", *args, **kwargs) -> None:
        super().__init__(message, *args, **kwargs)
        self.message = message or self.default_message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message})"


class InvalidUrlError(Error):
    """
    Raised when a URL is invalid
    """

    def __init__(self, url: str, *args, **kwargs) -> None:
        super().__init__(f'The URL "{url}" is invalid.', *args, **kwargs)
        self.url = url


class InvalidConfigurationError(Error):
    """
    Raised when a rate limiter configure call is invalid
    """

    default_message = (
        "Invalid configuration. A crawl delay or a request rate must be given."
    )
