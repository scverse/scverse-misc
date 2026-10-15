from __future__ import annotations

import inspect
import textwrap
import warnings
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

import pytest

pytest.importorskip("scverse_misc.sphinx_ext")
from docutils import nodes
from sphinx import addnodes

from scverse_misc import Deprecation, deprecated_arg, sphinx_ext
from scverse_misc.constants import ATTR_DEPRECATED, ATTR_DEPRECATED_ARG

if TYPE_CHECKING:
    from sphinx.application import Sphinx
    from sphinx.ext.napoleon import GoogleDocstring, NumpyDocstring  # type: ignore[attr-defined]
    from sphinx.testing.util import SphinxTestApp


@pytest.fixture(
    scope="session",
    params=[
        "no_docstring",
        "short",
        "long_googlestyle",
        "long_numpystyle",
        "no_param_desc_googlestyle",
        "no_param_desc_numpystyle",
    ],
)
def docstring(request: pytest.FixtureRequest, docstring_style: Literal["google", "numpy"]) -> str | None:
    match request.param:
        case "no_docstring":
            return None
        case "short":
            return "Test function"
        case "no_param_desc_numpystyle":
            if docstring_style == "google":
                pytest.skip("only google docstring parser enabled")
            return """Test function

            Parameters
            ----------
            positional_only_no_default
            positional_only_default
            positional_or_keyword_default
            keyword_only_default
                foobar
            """
        case "no_param_desc_googlestyle":
            if docstring_style == "numpy":
                pytest.skip("only numpy docstring parser enabled")
            return """Test function

            Args:
                positional_only_no_default:
                positional_only_default:
                positional_or_keyword_default:
                keyword_only_default: foobar
            """
        case "long_numpystyle":
            if docstring_style == "google":
                pytest.skip("only google docstring parser enabled")
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

            Returns
            -------
            This is a prose returns section.

            :attr:`~module.ClassName.attr1`
                First attribute
            :attr:`~module.ClassName.attr2`
                Second attribute
            """
        case "long_googlestyle":
            if docstring_style == "numpy":
                pytest.skip("only numpy docstring parser enabled")
            return """Test function

            This is a test.

            Args:
                positional_only_no_default: foo
                positional_only_default: bar lorem ipsum
                    test
                positional_or_keyword_default: baz
                keyword_only_default: foobar
            """
        case typ:
            pytest.fail(f"Unknown docstring style {typ}")


def test_deprecation_decorator(
    app: Sphinx, deprecated_func: Callable[..., int], docstring: str | None, msg: str | None
) -> None:
    lines = (inspect.getdoc(deprecated_func) or "").splitlines()
    sphinx_ext._process_deprecated_function(app, getattr(deprecated_func, ATTR_DEPRECATED), lines)
    offset = 0 if docstring is None else 2

    if docstring is not None:
        lines_orig = inspect.cleandoc(docstring).expandtabs().splitlines()
        assert lines[0] == lines_orig[0]
        assert len(lines[1].strip()) == 0, "expected empty line following summary"

        try:
            orig_returns_offset = lines_orig.index("Returns")
        except ValueError:
            pass
        else:
            returns_offset = lines.index("Returns")
            for roffset in range(max(len(lines_orig) - orig_returns_offset, len(lines) - returns_offset)):
                assert lines[returns_offset + roffset] == lines_orig[orig_returns_offset + roffset]

    assert lines[offset].startswith(".. version-deprecated")
    if msg is None:
        assert len(lines) == offset + 1 or not lines[offset + 1].startswith("   ")
    else:
        msg_lines = msg.splitlines()
        msg_indented = [f"   {line}" for line in msg_lines]
        assert lines[offset + 1 : offset + 1 + len(msg_lines)] == msg_indented


def _words(node: nodes.Element) -> list[str]:
    """Text of a node, ignoring whitespace and the separator before a parameter’s description."""
    return [word for word in node.astext().split() if word != "–"]


def _render_params(
    app: SphinxTestApp, parser: type[GoogleDocstring | NumpyDocstring], **docstrings: list[str]
) -> dict[str, dict[str, nodes.list_item]]:
    """Build each docstring as a `py:function` body, returning the rendered parameter items by name."""
    src = "Test\n====\n"
    for name, lines in docstrings.items():
        body = textwrap.indent("\n".join(parser(lines).lines()), "   ")
        src += f"\n.. py:function:: {name}()\n\n{body}\n"
    (app.srcdir / "index.rst").write_text(src)
    app.build()
    doctree = app.env.get_doctree("index")

    assert not list(doctree.findall(nodes.system_message)), "invalid rST"
    return {
        next(desc.findall(addnodes.desc_name)).astext(): {
            next(item.findall(addnodes.literal_strong)).astext(): item for item in desc.findall(nodes.list_item)
        }
        for desc in doctree.findall(addnodes.desc)
    }


@pytest.mark.parametrize(
    "arg",
    ("positional_only_no_default", "positional_only_default", "positional_or_keyword_default", "keyword_only_default"),
)
def test_deprecated_arg_decorator(
    app: SphinxTestApp,
    parser: type[GoogleDocstring | NumpyDocstring],
    func: Callable[..., int],
    msg: str | None,
    arg: str,
) -> None:
    deprecated_func = deprecated_arg(arg, Deprecation("2.718", msg or ""))(func)
    with pytest.warns(FutureWarning, match=f"{arg} is deprecated"):
        assert deprecated_func(1, 2, 3, keyword_only_default=4.0) == 42

    if arg != "positional_only_no_default":
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert deprecated_func(1) == 42

    if "\n" not in (func.__doc__ or ""):
        return

    lines = (inspect.getdoc(deprecated_func) or "").splitlines()
    sphinx_ext._process_deprecated_args(app, getattr(deprecated_func, ATTR_DEPRECATED_ARG), lines)
    rendered = _render_params(app, parser, before=(inspect.getdoc(func) or "").splitlines(), after=lines)

    # an insufficiently indented directive would show up as an extra parameter
    assert rendered["after"].keys() == rendered["before"].keys()

    notice = "Deprecated since version 2.718." if msg is None else f"Deprecated since version 2.718: {msg}"
    for name, item in rendered["after"].items():
        notices = list(item.findall(addnodes.versionmodified))
        assert [n.astext().split() for n in notices] == ([notice.split()] if name == arg else [])
        for n in notices:  # the rest of the parameter must be untouched
            n.parent.remove(n)
        assert _words(item) == _words(rendered["before"][name])
