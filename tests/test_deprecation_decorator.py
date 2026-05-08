import inspect
import warnings
from collections.abc import Callable
from typing import Literal, cast, get_args

import pytest
from sphinx.ext.napoleon import GoogleDocstring, NumpyDocstring  # type: ignore[attr-defined]

from scverse_misc import Deprecation, deprecated, deprecated_arg


@pytest.fixture(
    params=[
        pytest.param(None, id="no_message"),
        pytest.param("Test message.", id="short_message"),
        pytest.param("Test\nmessage.", id="long_message"),
    ]
)
def msg(request: pytest.FixtureRequest) -> str | None:
    return cast(str | None, request.param)


type DocstringStyles = Literal["no_docstring", "short", "long_numpystyle", "long_googlestyle"]


@pytest.fixture(params=get_args(DocstringStyles.__value__))
def docstring_style(request: pytest.FixtureRequest) -> DocstringStyles:
    return cast(DocstringStyles, request.param)


@pytest.fixture
def docstring(docstring_style: DocstringStyles) -> str | None:
    match docstring_style:
        case "no_docstring":
            return None
        case "short":
            return "Test function"
        case "long_numpystyle":
            return """Test function

            This is a test.

            Parameters
            ----------
            positional_only_no_default
                foo
            positional_only_default
                bar
            positional_or_keyword_default
                baz
            keyword_only_default
                foobar
            """
        case "long_googlestyle":
            return """Test function

            This is a test.

            Args:
                positional_only_no_default: foo
                positional_only_default: bar
                positional_or_keyword_default: baz
                keyword_only_default: foobar
            """


@pytest.fixture
def func(msg: str | None, docstring: str | None) -> Callable[..., int]:
    def _func(
        positional_only_no_default: int,
        positional_only_default: int = 1337,
        /,
        positional_or_keyword_default: int = 42,
        *,
        keyword_only_default: float = 3.1415,
    ) -> int:
        return 42

    _func.__doc__ = docstring
    return _func


@pytest.fixture
def deprecated_func(msg: str | None, func: Callable[..., int]) -> Callable[..., int]:
    return deprecated(Deprecation("foo", msg or ""))(func)


def test_deprecation_decorator(deprecated_func: Callable[..., int], docstring: str | None, msg: str | None) -> None:
    with pytest.warns(FutureWarning, match="deprecated"):
        assert deprecated_func(1, 2) == 42

    assert deprecated_func.__doc__ is not None
    lines = deprecated_func.__doc__.expandtabs().splitlines()
    offset = 0 if docstring is None else 2

    if docstring is not None:
        lines_orig = docstring.expandtabs().splitlines()
        assert lines[0] == lines_orig[0]
        assert len(lines[1].strip()) == 0, "expected empty line following summary"

    assert lines[offset].startswith(".. version-deprecated")
    if msg is None:
        assert len(lines) == offset + 1 or not lines[offset + 1].startswith("   ")
    else:
        msg_lines = msg.splitlines()
        msg_indented = [f"   {line}" for line in msg_lines]
        assert lines[offset + 1 : offset + 1 + len(msg_lines)] == msg_indented


@pytest.mark.parametrize(
    "arg",
    ("positional_only_no_default", "positional_only_default", "positional_or_keyword_default", "keyword_only_default"),
)
def test_deprecated_arg_decorator(
    func: Callable[..., int], msg: str | None, arg: str, docstring_style: DocstringStyles
) -> None:
    deprecated_func = deprecated_arg(arg, Deprecation("2.718", msg or ""))(func)
    with pytest.warns(FutureWarning, match=f"{arg} is deprecated"):
        assert deprecated_func(1, 2, 3, keyword_only_default=4.0) == 42

    if arg != "positional_only_no_default":
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert deprecated_func(1) == 42

    parser: type[NumpyDocstring] | type[GoogleDocstring] | None = None
    if docstring_style == "long_numpystyle":
        parser = NumpyDocstring
    elif docstring_style == "long_googlestyle":
        parser = GoogleDocstring

    if parser is None:
        return

    lines = parser(inspect.getdoc(deprecated_func) or "").lines()

    for i, line in enumerate(lines):
        if line.startswith(prefix := f":param {arg}: "):
            prefixlen = len(prefix)
            if msg is not None:
                stripped = lines[i + 1].strip()
                assert stripped == ".. version-deprecated:: 2.718"
                assert lines[i + 2][prefixlen:] == f"   {msg}"
                assert not lines[i + 3]
                assert lines[i + 4][:prefixlen] == " " * prefixlen
            else:
                assert line == f":param {arg}: .. version-deprecated:: 2.718"
                assert not lines[i + 1]
                assert lines[i + 2][:prefixlen] == " " * prefixlen
