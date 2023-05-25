class Error(Exception):
    """
    Base class for exceptions in this package
    """

    def __init__(self, message="", *args, **kwargs) -> None:
        super().__init__(message, *args, **kwargs)
        self.message = message

    def __repr__(self):
        return f"{self.__class__.__name__}({self.message})"


class InvalidUrlError(Error):
    """
    Raised when a URL is invalid
    """

    def __init__(self, url: str, *args, **kwargs) -> None:
        super().__init__(f'The URL "{url}" is invalid.', *args, **kwargs)
        self.url = url
