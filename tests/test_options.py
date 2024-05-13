from astel.options import DEFAULT_OPTIONS, merge_with_default_options


class DescribeMergeWithDefaultOptions:
    def it_adds_default_options(self):
        options = merge_with_default_options({"workers": 5})
        assert options == {**DEFAULT_OPTIONS, "workers": 5}  # type: ignore  # noqa: PGH003

    def it_returns_default_options_if_none(self):
        options = merge_with_default_options()
        assert options == DEFAULT_OPTIONS
