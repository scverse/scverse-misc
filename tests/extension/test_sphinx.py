from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("scverse_misc.sphinx_ext")
from sphinx.ext.autodoc import Options as AutodocOptions

from scverse_misc import make_register_namespace_decorator
from scverse_misc.sphinx_ext import _process_docstring

if TYPE_CHECKING:
    from sphinx.application import Sphinx
    from sphinx.ext.napoleon.docstring import GoogleDocstring, NumpyDocstring


class DummyClass: ...


reg_ns = make_register_namespace_decorator(DummyClass, "dummy")


def test_sphinx(app: Sphinx, parser: type[GoogleDocstring | NumpyDocstring]) -> None:
    lines = (inspect.getdoc(DummyClass) or "").splitlines()
    _process_docstring(app, "decorator", "tests.reg_ns", reg_ns, AutodocOptions(), lines)
    lines = parser(lines).lines()

    assert (
        lines[0]
        == "Decorator for registering custom functionality with a :class:`~tests.extension.test_sphinx.DummyClass` object."
    )
    assert "...     def __init__(self, dummy: DummyClass):" in lines
