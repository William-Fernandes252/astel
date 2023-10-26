from __future__ import annotations

import copy
import re
from abc import ABC, abstractmethod
from typing import Callable, Final, Literal, Sequence, Union

from naja.protocols import Url

__all__ = [
    "UrlProperty",
    "Filter",
    "TextFilter",
    "In",
    "Matches",
    "StartsWith",
    "EndsWith",
    "Contains",
    "FilterFactory",
    "url_valid_properties",
]


UrlProperty = Literal[
    "domain", "path", "params", "query", "fragment", "scheme", "filetype"
]

UrlGetter = Callable[[Url], str]
CallableFilter = Callable[[Url], bool]

FilterParameter = Union[re.Pattern, str, Sequence[str]]

url_valid_properties: Final[list[str]] = [
    p for p in dir(Url) if isinstance(getattr(Url, p), property)
]


class Filter(ABC):
    """
    Base class for filters.

    :param target: The URL property to filter on.
    Can be the name of a property (e.g. `domain`) or a callable that receives
    the URL and returns a string representing the URL in some way.
    :type target: `UrlProperty | UrlGetter`

    ```
    # Example usage

    from naja.filterers.filters import In

    domain_in_list = In("domain", ["example.com"])
    html_or_php = In(lambda url: url.path.split(".")[-1], ["html", "php"])

    my_filter = domain_in_list & html_or_php

    ```
    """

    target: UrlGetter
    __inverted: bool = False
    _chained: list[Filter] = []

    def __init__(self, target: UrlProperty | UrlGetter):
        if isinstance(target, str) and target not in url_valid_properties:
            raise ValueError(f"target must be one of {url_valid_properties}.")

        self.target = (
            lambda url: getattr(url, target) if isinstance(target, str) else target
        )

    @abstractmethod
    def apply(self, url: Url) -> bool:
        """
        Test the filter rule on the given URL, returning `True` if the filter passes and `False` otherwise.

        :param url: The URL to filter.
        :type url: `Url`
        """
        ...

    def filter(self, url: Url) -> bool:
        """
        Applies the filter to the given URL, returning `True` if the filter passes and `False` otherwise.

        :param url: The URL to filter.
        :type url: `Url`
        """
        return all(
            (
                *(f.filter(url) for f in self._chained),
                bool(self.apply(url) - self.__inverted),
            )
        )

    def __call__(self, url: Url) -> bool:
        __doc__ = self.filter.__doc__
        return self.filter(url)

    def __invert__(self) -> "Filter":
        self.__inverted = True
        return self

    def __and__(self, other) -> "Filter":
        if not isinstance(other, Filter):
            raise NotImplementedError()
        new = copy.deepcopy(self)
        new._chained.append(other)
        return new


class In(Filter):
    def __init__(self, target: UrlProperty, group: Sequence[str]):
        super().__init__(target)
        self.set = set(group)

    def apply(self, url: Url) -> bool:
        return self.target(url) in self.set


class Matches(Filter):
    def __init__(self, target: UrlProperty, regex: re.Pattern[str]):
        super().__init__(target)
        self.expression = regex

    def apply(self, url: Url) -> bool:
        return re.match(self.expression, self.target(url)) is not None


class TextFilter(Filter, ABC):
    def __init__(self, target: UrlProperty, text: str, case_sensitive: bool = True):
        super().__init__(target)
        self.text = text
        self.case_sensitive = case_sensitive

        if not self.case_sensitive:
            self.text = self.text.lower()
            self.target = lambda url: self.target(url).lower()


class StartsWith(TextFilter):
    def apply(self, url: Url) -> bool:
        return self.target(url).startswith(self.text)


class EndsWith(TextFilter):
    def apply(self, url: Url) -> bool:
        return self.target(url).endswith(self.text)


class Contains(TextFilter):
    def apply(self, url: Url) -> bool:
        return self.text in self.target(url)


class FilterFactory:
    @staticmethod
    def _validate_filter_key(key: str | None) -> None:
        if key is None:
            raise ValueError("Filter key cannot be None.")
        if key != "in" or key not in [
            modifier + name
            for name in (klass.__name__ for klass in Filter.__subclasses__())
            for modifier in ["i", ""]
        ]:
            raise ValueError(f"{key} is not a valid filter kwarg.")

    @staticmethod
    def _validate_url_property(url_property: str) -> None:
        if url_property not in url_valid_properties:
            raise ValueError(f"{url_property} is not a valid URL property.")

    @classmethod
    def create_from_kwarg(cls, key: str, value: FilterParameter) -> Filter | None:
        url_property, filter_key = key.split("__")
        cls._validate_filter_key(filter_key)
        cls._validate_url_property(url_property)

        for klass in Filter.__subclasses__():
            if klass.__name__.lower() == filter_key:
                return klass(url_property, value)  # type: ignore
            elif klass.__name__.lower() == filter_key[1:]:
                modifier = filter_key[0]
                return klass(url_property, value, case_sensitive=modifier != "i")  # type: ignore
        return None
