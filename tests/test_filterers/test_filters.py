from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import List, Type

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
from naja.protocols import Url
from tests.strategies import filter_kwargs, filters, url_properties, urls


class FilterTest(ABC):
    @property
    @abstractmethod
    def filter_class(self) -> Type[Filter]: ...


class TestIn(FilterTest):
    @property
    def filter_class(self) -> Type[In]:
        return In

    @given(
        property=url_properties(),
        examples=strategies.lists(
            urls().map(lambda url: url.raw), max_size=10, min_size=1
        ),
        sample_url=urls(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=10)
    def it_checks_if_property_value_is_in_examples(
        self,
        property,
        examples: List[str],
        sample_url: Url,
        expected: bool,
    ):
        assume(
            getattr(sample_url, property) in examples
            if expected
            else getattr(sample_url, property) not in examples
        )
        f = self.filter_class(property, examples)
        assert f.filter(sample_url) == expected

    @given(
        property=url_properties(),
        examples=strategies.lists(
            urls().map(lambda url: url.raw), min_size=1, max_size=10
        ),
        sample_url=urls(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=3)
    def it_should_filter_out_if_property_value_is_not_in_examples_when_inverted(
        self,
        property,
        examples: List[str],
        sample_url: Url,
        expected: bool,
    ):
        assume(
            getattr(sample_url, property) in examples
            if not expected
            else getattr(sample_url, property) not in examples
        )
        f = ~self.filter_class(property, examples)
        assert f.filter(sample_url) == expected


class TestMatches(FilterTest):
    @property
    def filter_class(self) -> Type[Matches]:
        return Matches

    @given(
        property=url_properties(),
        sample_url=urls(),
        expected=strategies.booleans(),
    )
    @pytest.mark.parametrize("regex", [re.compile(r"^\w+://")])
    @settings(max_examples=10)
    def it_should_check_if_property_value_matches_regex(
        self, property, regex: re.Pattern, sample_url: Url, expected: bool
    ):
        assume(bool(regex.match(getattr(sample_url, property))) == expected)
        assume(isinstance(regex.pattern, str))
        f = self.filter_class(property, regex)
        assert f.filter(sample_url) == expected

    @given(
        property=url_properties(),
        sample_url=urls(),
        expected=strategies.booleans(),
    )
    @pytest.mark.parametrize("regex", [re.compile(r"^\w+://")])
    @settings(max_examples=10)
    def it_should_filter_out_if_property_value_does_not_match_regex_when_inverted(
        self, property, regex: re.Pattern, sample_url: Url, expected: bool
    ):
        assume(bool(regex.match(getattr(sample_url, property))) != expected)
        f = ~self.filter_class(property, regex)
        assert f.filter(sample_url) == expected


class TestStartsWith(FilterTest):
    @property
    def filter_class(self) -> Type[StartsWith]:
        return StartsWith

    @given(
        property=url_properties(),
        sample_url=urls(),
        prefix=strategies.text(min_size=1),
        case_insensitive=strategies.booleans(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=10)
    def it_should_check_if_property_value_starts_with_prefix(
        self,
        property: UrlProperty,
        sample_url: Url,
        prefix: str,
        case_insensitive: bool,
        expected: bool,
    ):
        property_value: str = getattr(sample_url, property)
        assume(property_value.startswith(prefix) == expected)
        f = self.filter_class(property, prefix, case_insensitive)
        assert f.filter(sample_url) == expected

    @given(
        property=url_properties(),
        sample_url=urls(),
        prefix=strategies.text(min_size=1),
        case_insensitive=strategies.booleans(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=10)
    def it_should_filter_out_if_property_value_does_not_start_with_prefix_when_inverted(
        self,
        property: UrlProperty,
        sample_url: Url,
        prefix: str,
        case_insensitive: bool,
        expected: bool,
    ):
        property_value: str = getattr(sample_url, property)
        assume(property_value.startswith(prefix) != expected)
        f = ~self.filter_class(property, prefix, case_insensitive)
        assert f.filter(sample_url) == expected


class TestEndsWith(FilterTest):
    @property
    def filter_class(self) -> Type[EndsWith]:
        return EndsWith

    @given(
        property=url_properties(),
        sample_url=urls(),
        suffix=strategies.text(min_size=1),
        case_insensitive=strategies.booleans(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=10)
    def it_should_check_if_property_value_ends_with_suffix(
        self,
        property: UrlProperty,
        sample_url: Url,
        suffix: str,
        case_insensitive: bool,
        expected: bool,
    ):
        property_value: str = getattr(sample_url, property)
        assume(property_value.endswith(suffix) == expected)
        f = self.filter_class(property, suffix, case_insensitive)
        assert f.filter(sample_url) == expected

    @given(
        property=url_properties(),
        sample_url=urls(),
        suffix=strategies.text(min_size=1),
        case_insensitive=strategies.booleans(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=10)
    def it_should_filter_out_if_property_value_does_not_end_with_suffix_when_inverted(
        self,
        property: UrlProperty,
        sample_url: Url,
        suffix: str,
        case_insensitive: bool,
        expected: bool,
    ):
        property_value: str = getattr(sample_url, property)
        assume(property_value.endswith(suffix) != expected)
        f = ~self.filter_class(property, suffix, case_insensitive)
        assert f.filter(sample_url) == expected


class TestContains(FilterTest):
    @property
    def filter_class(self) -> Type[Contains]:
        return Contains

    @given(
        property=url_properties(),
        sample_url=urls(),
        text=strategies.text(min_size=1),
        case_insensitive=strategies.booleans(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=10)
    def it_should_check_if_property_value_contains_text(
        self,
        property: UrlProperty,
        sample_url: Url,
        text: str,
        case_insensitive: bool,
        expected: bool,
    ):
        assume((text in getattr(sample_url, property)) == expected)
        f = self.filter_class(property, text, case_insensitive)
        assert f.filter(sample_url) == expected

    @given(
        property=url_properties(),
        sample_url=urls(),
        text=strategies.text(min_size=1),
        case_insensitive=strategies.booleans(),
        expected=strategies.booleans(),
    )
    @settings(max_examples=10)
    def it_should_filter_out_if_property_value_does_not_contain_text_when_inverted(
        self,
        property: UrlProperty,
        sample_url: Url,
        text: str,
        case_insensitive: bool,
        expected: bool,
    ):
        assume((text not in getattr(sample_url, property)) == expected)
        f = ~self.filter_class(property, text, case_insensitive)
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
