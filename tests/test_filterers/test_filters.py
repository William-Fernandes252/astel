from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Type

import pytest
from hypothesis import assume, given, settings, strategies

from naja.filters import (
    Contains,
    EndsWith,
    Filter,
    In,
    Matches,
    StartsWith,
    UrlProperty,
    create_from_kwarg,
)
from tests.strategies import filter_kwargs, filters, url_properties, urls

if TYPE_CHECKING:
    from naja.protocols import Url


class FilterTest(ABC):
    @property
    @abstractmethod
    def filter_class(self) -> Type[Filter]: ...


class TestIn(FilterTest):
    @property
    def filter_class(self) -> Type[In]:
        return In

    @given(
        url_prop=url_properties(),
        examples=strategies.lists(
            urls().map(lambda url: url.raw), max_size=10, min_size=1
        ),
        sample_url=urls(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=10)
    def it_checks_if_url_prop_value_is_in_examples(
        self,
        url_prop: UrlProperty,
        examples: list[str],
        sample_url: Url,
        expected: bool,
    ):
        assume(
            getattr(sample_url, url_prop) in examples
            if expected
            else getattr(sample_url, url_prop) not in examples
        )
        f = self.filter_class(url_prop, examples)
        assert f.filter(sample_url) == expected

    @given(
        url_prop=url_properties(),
        examples=strategies.lists(
            urls().map(lambda url: url.raw), min_size=1, max_size=10
        ),
        sample_url=urls(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=3)
    def it_should_filter_out_if_url_prop_value_is_not_in_examples_when_inverted(
        self,
        url_prop: UrlProperty,
        examples: list[str],
        sample_url: Url,
        expected: bool,
    ):
        assume(
            getattr(sample_url, url_prop) in examples
            if not expected
            else getattr(sample_url, url_prop) not in examples
        )
        f = ~self.filter_class(url_prop, examples)
        assert f.filter(sample_url) == expected


class TestMatches(FilterTest):
    @property
    def filter_class(self) -> type[Matches]:
        return Matches

    @given(
        url_prop=url_properties(),
        sample_url=urls(),
        expected=strategies.booleans(),
    )
    @pytest.mark.parametrize("regex", [re.compile(r"^\w+://")])
    @settings(max_examples=10)
    def it_should_check_if_url_prop_value_matches_regex(
        self, url_prop: UrlProperty, regex: re.Pattern, sample_url: Url, expected: bool
    ):
        assume(bool(regex.match(getattr(sample_url, url_prop))) == expected)
        assume(isinstance(regex.pattern, str))
        f = self.filter_class(url_prop, regex)
        assert f.filter(sample_url) == expected

    @given(
        url_prop=url_properties(),
        sample_url=urls(),
        expected=strategies.booleans(),
    )
    @pytest.mark.parametrize("regex", [re.compile(r"^\w+://")])
    @settings(max_examples=10)
    def it_should_filter_out_if_url_prop_value_does_not_match_regex_when_inverted(
        self, url_prop: UrlProperty, regex: re.Pattern, sample_url: Url, expected: bool
    ):
        assume(bool(regex.match(getattr(sample_url, url_prop))) != expected)
        f = ~self.filter_class(url_prop, regex)
        assert f.filter(sample_url) == expected


class TestStartsWith(FilterTest):
    @property
    def filter_class(self) -> type[StartsWith]:
        return StartsWith

    @given(
        url_prop=url_properties(),
        sample_url=urls(),
        prefix=strategies.text(min_size=1),
        case_sensitive=strategies.booleans(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=10)
    def it_should_check_if_url_prop_value_starts_with_prefix(
        self,
        url_prop: UrlProperty,
        sample_url: Url,
        prefix: str,
        case_sensitive: bool,
        expected: bool,
    ):
        url_prop_value: str = getattr(sample_url, url_prop)
        assume(url_prop_value.startswith(prefix) == expected)
        f = self.filter_class(url_prop, prefix, case_sensitive=case_sensitive)
        assert f.filter(sample_url) == expected

    @given(
        url_prop=url_properties(),
        sample_url=urls(),
        prefix=strategies.text(min_size=1),
        case_sensitive=strategies.booleans(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=10)
    def it_should_filter_out_if_url_prop_value_does_not_start_with_prefix_when_inverted(
        self,
        url_prop: UrlProperty,
        sample_url: Url,
        prefix: str,
        case_sensitive: bool,
        expected: bool,
    ):
        url_prop_value: str = getattr(sample_url, url_prop)
        assume(url_prop_value.startswith(prefix) != expected)
        f = ~self.filter_class(url_prop, prefix, case_sensitive=case_sensitive)
        assert f.filter(sample_url) == expected


class TestEndsWith(FilterTest):
    @property
    def filter_class(self) -> type[EndsWith]:
        return EndsWith

    @given(
        url_prop=url_properties(),
        sample_url=urls(),
        suffix=strategies.text(min_size=1),
        case_sensitive=strategies.booleans(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=10)
    def it_should_check_if_url_prop_value_ends_with_suffix(
        self,
        url_prop: UrlProperty,
        sample_url: Url,
        suffix: str,
        case_sensitive: bool,
        expected: bool,
    ):
        url_prop_value: str = getattr(sample_url, url_prop)
        assume(url_prop_value.endswith(suffix) == expected)
        f = self.filter_class(url_prop, suffix, case_sensitive=case_sensitive)
        assert f.filter(sample_url) == expected

    @given(
        url_prop=url_properties(),
        sample_url=urls(),
        suffix=strategies.text(min_size=1),
        case_sensitive=strategies.booleans(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=10)
    def it_should_filter_out_if_url_prop_value_does_not_end_with_suffix_when_inverted(
        self,
        url_prop: UrlProperty,
        sample_url: Url,
        suffix: str,
        case_sensitive: bool,
        expected: bool,
    ):
        url_prop_value: str = getattr(sample_url, url_prop)
        assume(url_prop_value.endswith(suffix) != expected)
        f = ~self.filter_class(url_prop, suffix, case_sensitive=case_sensitive)
        assert f.filter(sample_url) == expected


class TestContains(FilterTest):
    @property
    def filter_class(self) -> type[Contains]:
        return Contains

    @given(
        url_prop=url_properties(),
        sample_url=urls(),
        text=strategies.text(min_size=1),
        case_sensitive=strategies.booleans(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=10)
    def it_should_check_if_url_prop_value_contains_text(
        self,
        url_prop: UrlProperty,
        sample_url: Url,
        text: str,
        case_sensitive: bool,
        expected: bool,
    ):
        assume((text in getattr(sample_url, url_prop)) == expected)
        f = self.filter_class(url_prop, text, case_sensitive=case_sensitive)
        assert f.filter(sample_url) == expected

    @given(
        url_prop=url_properties(),
        sample_url=urls(),
        text=strategies.text(min_size=1),
        case_sensitive=strategies.booleans(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=10)
    def it_should_filter_out_if_url_prop_value_does_not_contain_text_when_inverted(
        self,
        url_prop: UrlProperty,
        sample_url: Url,
        text: str,
        case_sensitive: bool,
        expected: bool,
    ):
        assume((text not in getattr(sample_url, url_prop)) == expected)
        f = ~self.filter_class(url_prop, text, case_sensitive=case_sensitive)
        assert f.filter(sample_url) == expected


class TestFilter:
    @given(filters(), urls())
    def it_should_apply_filter_to_url(self, f: Filter, url: Url):
        assert f(url) == f.filter(url)

    @given(filters(), filters(), urls())
    def it_should_chain_filters(self, f1: Filter, f2: Filter, url: Url):
        chained = f1 & f2
        assert chained(url) == (f1(url) and f2(url))

    @given(filters(), urls())
    def it_should_invert_filter(self, f: Filter, url: Url):
        inverted = ~f
        assert inverted(url) == (not f(url))


class TestCreateFromKwargs:
    @given(filter_kwargs())
    def it_should_create_a_filter_instance(self, kwargs: dict):
        for key, value in kwargs.items():
            f = create_from_kwarg(key, value)
            assert isinstance(f, Filter)
