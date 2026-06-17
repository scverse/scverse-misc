from pathlib import Path

import pytest

pytest_plugins = ["sphinx.testing.fixtures"]


@pytest.fixture(scope="session", autouse=True)
def _sphinx_config(sphinx_test_tempdir: Path) -> None:
    """Since we only need one, we use this instead of static roots like `@pytest.mark.sphinx('html', testroot="mybook")`."""
    p = sphinx_test_tempdir / "root" / "conf.py"
    p.parent.mkdir(parents=True)
    p.write_text("""
extensions = ["sphinx.ext.autodoc", "scverse_misc.sphinx_ext", "sphinx.ext.napoleon", "sphinx_autodoc_typehints"]
typehints_defaults = "braces"
""")
