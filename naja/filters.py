from __future__ import annotations

import copy
import functools
import inspect
import operator
import re
from abc import ABC, abstractmethod
from typing import (
    Callable,
    Final,
    Generic,
    Literal,
    Sequence,
    Type,
    TypeVar,
    Union,
    cast,
)

from naja.parsers import Url

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

T = TypeVar("T", re.Pattern, str, Sequence[str], Union[re.Pattern, str])

UrlProperty = Literal[
    "domain", "path", "params", "query", "fragment", "scheme", "filetype"
]

CallableFilter = Callable[[Url], bool]

url_valid_properties: Final[list[str]] = [
    p for p in dir(Url) if isinstance(getattr(Url, p), property)
]


class Filter(ABC, Generic[T]):
    """
    Base class for filters.

    ### Example usage

    ```python
    from naja.filterers.filters import In

    domain_in_list = In("domain", ["example.com"])
    html_or_php = In(lambda url: url.path.split(".")[-1], ["html", "php"])

    my_filter = domain_in_list & html_or_php

    ```
    """

    url_prop: UrlProperty
    __inverted: bool
    _chained: list[Filter]
    param: T | None

    def __init__(
        self,
        url_prop: UrlProperty,
        param: T | None = None,
        *,
        _inverted: bool = False,
        _chained: list[Filter] | None = None,
    ) -> None:
        """Initializes the filter with the given URL property."""
        self.param = param
        self.url_prop = url_prop
        self.__inverted = _inverted
        self._chained = _chained or []

    @abstractmethod
    def _apply(self, url: Url) -> bool:
        """Test the filter rule on the given URL.

        Args:
            url (Url): The URL to test the filter on.

        Returns:
            bool: True if the URL passes the filter, False otherwise.
        """
        ...

    def _get_url_property(self, url: Url) -> str:
        """Return the URL property value for the given URL.

        Args:
            url (Url): The URL to get the property from.

        Returns:
            str: The URL property value.
        """
        return getattr(url, self.url_prop)

    def filter(self, url: Url) -> bool:
        """Applies the filter to the given URL.

        Args:
            url (Url): The URL to filter.

        Returns:
            bool: True if the URL passes the filter, False otherwise.
        """
        return all(
            (
                *(f.filter(url) for f in self._chained),
                bool(self._apply(url) - self.__inverted),
            )
        )

    def __call__(self, url: Url) -> bool:
        return self.filter(url)

    def __invert__(self) -> Filter:
        new = copy.deepcopy(self)
        new.__inverted = not self.__inverted  # noqa: SLF001
        return new

    def __and__(self, other: Filter) -> Filter:
        if not isinstance(other, Filter):
            raise NotImplementedError
        new = copy.deepcopy(self)
        new._chained.append(other)
        return new


class In(Filter[Sequence[str]]):
    def __init__(self, url_prop: UrlProperty, group: Sequence[str], **kwargs) -> None:
        super().__init__(url_prop, **kwargs)
        self.set = set(group)

    def _apply(self, url: Url) -> bool:
        return self._get_url_property(url) in self.set


class Matches(Filter[Union[re.Pattern, str]]):
    def __init__(
        self, url_prop: UrlProperty, regex: re.Pattern | str, **kwargs
    ) -> None:
        super().__init__(url_prop, regex, **kwargs)
        self.regex = re.compile(regex) if isinstance(regex, str) else regex

    def _apply(self, url: Url) -> bool:
        return re.match(self.regex, self._get_url_property(url)) is not None


class TextFilter(Filter, ABC):
    def __init__(
        self, url_prop: UrlProperty, text: str, *, case_sensitive: bool = True, **kwargs
    ) -> None:
        super().__init__(url_prop, **kwargs)
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
    start_from: type[Filter] = Filter, initial: list[type[Filter]] | None = None
) -> list[type[Filter]]:
    """Get all subclasses of a given class.

    Args:
        start_from (type[Filter], optional): The class to start from.
        Defaults to Filter.
        initial (list[type[Filter]] | None, optional): The initial found
        children. Defaults to None.

    Returns:
        list[type[Filter]]: _description_
    """
    initial = initial or []
    if len(start_from.__subclasses__()) == 0 and not inspect.isabstract(start_from):
        if start_from not in initial:
            initial.append(start_from)
        return initial
    return [
        *initial,
        *functools.reduce(
            operator.iadd,
            (
                _get_filter_subclasses(subclass, initial)
                for subclass in start_from.__subclasses__()
            ),
            [],
        ),
    ]


def _validate_filter_key(key: str | None) -> str:
    """Validate the filter key.

    Args:
        key (str | None): The key to validate.

    Raises:
        ValueError: If no key is provided.
        ValueError: If the key is not valid.

    Returns:
        str: The validated key.
    """
    if key is None:
        msg = "Filter key cannot be None."
        raise ValueError(msg)

    if key != "in" and key not in [
        (modifier + name)
        for modifier in ["i", ""]
        for name in (klass.__name__.lower() for klass in _get_filter_subclasses())
    ]:
        msg = f'"{key}" is not a valid filter kwarg.'
        raise ValueError(msg)

    return key


def _validate_url_property(value: str) -> UrlProperty:
    """Validate the URL property.

    Args:
        value (str): the URL property to validate.

    Raises:
        ValueError: If the URL property is not valid.

    Returns:
        UrlProperty: The validated URL property.
    """
    if value not in url_valid_properties:
        msg = f"{value} is not a valid URL property."
        raise ValueError(msg)
    return cast(UrlProperty, value)


def create_from_kwarg(key: str, value: T) -> Filter | None:
    """Create a filter from a key-value pair.

    Args:
        key (str): The key to create the filter from.
        value (FilterParameter): The filter parameter.

    Returns:
        Filter | None: The created filter or None if the key is invalid.
    """
    url_prop, filter_key = key.split("__")
    filter_key = _validate_filter_key(filter_key)
    url_prop = _validate_url_property(url_prop)

    for klass in _get_filter_subclasses():
        if klass.__name__.lower() == filter_key:
            return klass(url_prop, value)
        if klass.__name__.lower() == filter_key[1:]:
            klass = cast(Type[TextFilter], klass)
            if not isinstance(value, str):
                msg = f"Expected a string value for {klass.__name__} filter."
                raise ValueError(msg)
            modifier = filter_key[0]
            return klass(url_prop, value, case_sensitive=modifier != "i")
    return None
