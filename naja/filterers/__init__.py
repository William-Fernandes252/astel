import re
from collections.abc import Sequence
from typing import Self, get_args

from naja.protocols import Url

from .filters import (
    Contains,
    EndsWith,
    Filter,
    FilterFactory,
    FilterParameter,
    In,
    Matches,
    StartsWith,
    UrlGetter,
    UrlProperty,
)

__all__ = [
    "Filter",
    "Contains",
    "EndsWith",
    "In",
    "Matches",
    "StartsWith",
    "UrlProperty",
    "UrlFilterer",
    "UrlGetter",
]


class UrlFilterer:
    filters: set[Filter] = set()

    def __init__(
        self,
        filter_factory: type[FilterFactory] = FilterFactory,
        **kwargs: FilterParameter,
    ):
        self.filter_factory = filter_factory
        for key, value in kwargs.items():
            if f := self.filter_factory.create_from_kwarg(key, value):
                self.filters.add(f)

    def filter(self, condition: Filter | None, **kwargs: FilterParameter) -> Self:
        if condition is not None and len(kwargs) > 0:
            raise ValueError(
                "Only one of condition and filter kwargs can be specified."
            )
        elif condition is not None:
            if not isinstance(condition, Filter):
                raise ValueError(f"condition must be a {Filter.__name__} instance.")
            self.filters.add(condition)
        elif kwargs:
            for key, value in kwargs.items():
                if f := self.filter_factory.create_from_kwarg(key, value):
                    self.filters.add(f)
        return self

    def process(self, url: Url) -> Url | None:
        return url if all(f(url) for f in self.filters) else None
