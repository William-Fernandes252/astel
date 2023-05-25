from pathlib import Path
from urllib import parse

__all__ = ["UrlFilterer"]


class UrlFilterer:
    def __init__(
        self,
        allowed_domains: set[str] | None = None,
        allowed_schemes: set[str] | None = None,
        allowed_filetypes: set[str] | None = None,
    ):
        self.allowed_domains = allowed_domains
        self.allowed_schemes = allowed_schemes
        self.allowed_filetypes = allowed_filetypes

    def filter_url(self, base: str, url: str | None) -> str | None:
        url = parse.urljoin(base, url)
        url, _ = parse.urldefrag(url)
        parsed = parse.urlparse(url)

        if (
            self.allowed_schemes is not None
            and parsed.scheme not in self.allowed_schemes
        ):
            return None
        if (
            self.allowed_domains is not None
            and parsed.netloc not in self.allowed_domains
        ):
            return None
        if (
            self.allowed_filetypes is not None
            and Path(parsed.path).suffix not in self.allowed_filetypes
        ):
            return None

        return url
