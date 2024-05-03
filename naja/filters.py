from __future__ import annotations

import copy
import inspect
import re
from abc import ABC, abstractmethod
from typing import Callable, Final, Literal, Sequence, Type, Union

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
    "url_valid_properties",
]


UrlProperty = Literal[
    "domain", "path", "params", "query", "fragment", "scheme", "filetype"
]

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

    property: UrlProperty
    __inverted: bool = False
    _chained: list[Filter]

    def __init__(self, property: UrlProperty):
        """Initializes the filter with the given url target function or property.

        :param target: The URL property to filter on.
        Can be the name of a property (e.g. `domain`) or a callable that receives a
        URL and returns a string representing the URL in some way.
        :type target: `UrlProperty | UrlGetter`
        """
        self.property = property
        self._chained = []

    @abstractmethod
    def _apply(self, url: Url) -> bool:
        """
        Test the filter rule on the given URL.

        :param url: The URL to filter.
        :type url: `Url`
        """
        ...

    def _get_url_property(self, url: Url) -> str:
        """Return the URL property value for the given URL.

        Args:
            url (Url): The URL to get the property from.

        Returns:
            str: The URL property value.
        """
        return getattr(url, self.property)

    def filter(self, url: Url) -> bool:
        """
        Applies the filter to the given URL.

        :param url: The URL to filter.
        :type url: `Url`
        """
        return all(
            (
                *(f.filter(url) for f in self._chained),
                bool(self._apply(url) - self.__inverted),
            )
        )

    def __call__(self, url: Url) -> bool:
        return self.filter(url)

    def __invert__(self) -> "Filter":
        new = copy.deepcopy(self)
        new.__inverted = True
        return new

    def __and__(self, other) -> "Filter":
        if not isinstance(other, Filter):
            raise NotImplementedError()
        new = copy.deepcopy(self)
        new._chained.append(other)
        return new


class In(Filter):
    def __init__(self, property: UrlProperty, group: Sequence[str]):
        super().__init__(property)
        self.set = set(group)

    def _apply(self, url: Url) -> bool:
        return self._get_url_property(url) in self.set


class Matches(Filter):
    def __init__(self, property: UrlProperty, regex: re.Pattern | str):
        super().__init__(property)
        self.expression = regex

    def _apply(self, url: Url) -> bool:
        return re.match(self.expression, self._get_url_property(url)) is not None


class TextFilter(Filter, ABC):
    def __init__(self, property: UrlProperty, text: str, case_sensitive: bool = True):
        super().__init__(property)
        self.case_sensitive = case_sensitive
        if not self.case_sensitive:
            text = text.lower()
        self.text = text

    def _get_url_property(self, url: Url) -> str:
        return (
            super()._get_url_property(url)
            if self.case_sensitive
            else super()._get_url_property(url).lower()
        )


class StartsWith(TextFilter):
    def _apply(self, url: Url) -> bool:
        return self._get_url_property(url).startswith(self.text)


class EndsWith(TextFilter):
    def _apply(self, url: Url) -> bool:
        return self._get_url_property(url).endswith(self.text)


class Contains(TextFilter):
    def _apply(self, url: Url) -> bool:
        return self.text in self._get_url_property(url)


def _get_filter_subclasses(
    start_from=Filter, initial: list[Type[Filter]] | None = None
) -> list[Type[Filter]]:
    initial = initial or []
    if len(start_from.__subclasses__()) == 0 and not inspect.isabstract(start_from):
        if start_from not in initial:
            initial.append(start_from)
        return initial
    return [
        *initial,
        *sum(
            (
                _get_filter_subclasses(subclass, initial)
                for subclass in start_from.__subclasses__()
            ),
            [],
        ),
    ]


def _validate_filter_key(key: str | None) -> None:
    if key is None:
        raise ValueError("Filter key cannot be None.")

    if key != "in" and key not in [
        (modifier + name)
        for modifier in ["i", ""]
        for name in (klass.__name__.lower() for klass in _get_filter_subclasses())
    ]:
        raise ValueError(f'"{key}" is not a valid filter kwarg.')


def _validate_url_property(url_property: str) -> None:
    if url_property not in url_valid_properties:
        raise ValueError(f"{url_property} is not a valid URL property.")


def create_from_kwarg(key: str, value: FilterParameter) -> Filter | None:
    url_property, filter_key = key.split("__")
    _validate_filter_key(filter_key)
    _validate_url_property(url_property)

    for klass in _get_filter_subclasses():
        if klass.__name__.lower() == filter_key:
            return klass(url_property, value)  # type: ignore
        elif klass.__name__.lower() == filter_key[1:]:
            modifier = filter_key[0]
            return klass(
                url_property, value, case_sensitive=modifier != "i"  # type: ignore
            )
    return None
