import re
from collections.abc import Sequence
from typing import Self, get_args

from naja.protocols import Url

from .filters import Contains, EndsWith, Filter, In, Matches, StartsWith, UrlProperty

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

FilterParameter = re.Pattern[str] | str | Sequence[str]


class UrlFilterer:
    filters: set[Filter] = set()

    @staticmethod
    def _parse_filter_kwarg(key: str, value: FilterParameter) -> Filter:
        result = re.match(r"^([a-z]+)__(i?)([a-z]+)$", key)
        if result:
            if url_property := result.groups()[1] not in get_args(UrlProperty):
                raise ValueError(f"{url_property} is not a valid URL property.")

            match result.groups()[1:]:
                case (attribute, "i", "n"):
                    if not isinstance(value, Sequence):
                        raise ValueError(f"{value} is not a valid sequence.")
                    return In(attribute, value)  # type: ignore
                case (attribute, None, "matches"):
                    if type(value) not in [str, re.Pattern]:
                        raise ValueError(f"{value} is not a valid regex.")
                    return Matches(attribute, value)  # type: ignore
                case (attribute, modifier, text_filter):
                    text_filters_classes: Sequence[type] = [
                        StartsWith,
                        EndsWith,
                        Contains,
                    ]
                    for filter_class in text_filters_classes:
                        if filter_class.__name__ == text_filter:
                            return filter_class(
                                attribute, value, case_sensitive=modifier != "i"
                            )

        raise ValueError(f"{key} is not a valid filter kwarg.")

    def __init__(self, **kwargs: FilterParameter):
        for key, value in kwargs.items():
            self.filters.add(self._parse_filter_kwarg(key, value))

    def filter(self, condition: Filter | None, **kwargs: FilterParameter) -> Self:
        if condition or kwargs:
            if condition and kwargs:
                raise ValueError(
                    "Only one of condition and filter kwargs can be specified."
                )
            elif condition is not None:
                if not isinstance(condition, Filter):
                    raise ValueError(f"condition must be a {Filter.__name__} instance.")
                self.filters.add(condition)
            elif kwargs:
                key, value = kwargs.popitem()
                self.filters.add(self._parse_filter_kwarg(key, value))

        return self

    def process(self, url: Url) -> Url | None:
        return url if all(f(url) for f in self.filters) else None
