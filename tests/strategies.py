import inspect
from typing import Any, Type

from hypothesis import provisional, strategies

from naja.filters import (
    Filter,
    In,
    Matches,
    TextFilter,
    UrlProperty,
    url_valid_properties,
)
from naja.parsers import UrlParserMixin
from naja.protocols import Url


@strategies.composite
def url_properties(draw: strategies.DrawFn) -> UrlProperty:
    """Strategy to generate a url getter.

    Returns:
        UrlGetter: Function that receives a Url and returns a string.
    """
    return draw(strategies.sampled_from(url_valid_properties))


@strategies.composite
def urls(draw: strategies.DrawFn) -> Url:
    """Strategy to generate a url object.

    Returns:
        Url: A url object.
    """
    return draw(strategies.builds(UrlParserMixin.parse_url, provisional.urls()))


@strategies.composite
def _f_classes(draw: strategies.DrawFn) -> Type[Filter]:
    return draw(
        strategies.one_of(
            [
                strategies.just(klass)
                for klass in Filter.__subclasses__()
                if not inspect.isabstract(klass)
            ]
        )
    )


@strategies.composite
def filters(
    draw: strategies.DrawFn,
    props: strategies.SearchStrategy[UrlProperty] = url_properties(),
) -> Filter:
    """Strategy to generate a filter.

    Args:
        props (strategies.SearchStrategy[UrlProperty], optional): A strategy to generate
        the url property. Defaults to `url_properties`.
        strategy to generate the url getter. Defaults to strategies.just("domain").

    Returns:
        Filter: A filter object.
    """
    f_class = draw(_f_classes())
    prop = draw(props)
    if issubclass(f_class, In):
        examples = draw(strategies.lists(strategies.text(min_size=1, max_size=10)))
        return f_class(prop, examples)
    if issubclass(f_class, Matches):
        regex = draw(strategies.just(r"^\w+://"))
        return f_class(prop, regex)
    if issubclass(f_class, TextFilter):
        text = draw(strategies.text(min_size=1, max_size=10))
        case_insensitive = draw(strategies.booleans())
        return f_class(prop, text, case_insensitive)
    return f_class(prop)


@strategies.composite
def filter_kwargs(draw: strategies.DrawFn):
    """Strategy to generate filter kwargs.

    Returns:
        dict: A dictionary with filter kwargs.
    """
    url_prop = draw(url_properties())
    f_class = draw(_f_classes())

    if issubclass(f_class, TextFilter):
        case_sensitive = draw(strategies.booleans())
        key = f"{url_prop}__{'i' if case_sensitive else ''}{f_class.__name__.lower()}"
    key = f"{url_prop}__{f_class.__name__.lower()}"

    value: Any = None
    if issubclass(f_class, In):
        value = draw(strategies.lists(strategies.text(min_size=1, max_size=10)))
    if issubclass(f_class, Matches):
        value = draw(strategies.just(r"^\w+://"))
    if issubclass(f_class, TextFilter):
        value = draw(strategies.text(min_size=1, max_size=10))

    return {key: value}
