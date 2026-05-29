# Sphinx extension
This package provides a Sphinx extension to create or adjust documentation.
For example, using the [deprecated decorator](#scverse_misc.deprecated) adds a deprecation notice to the function's description.
To use the extension, add `"scverse_misc.sphinx_ext"` to your extensions array in `conf.py`.
The extension requires `scverse_misc` to be installed with the `sphinx` extra.

:::{important}
The `scverse_misc.sphinx_ext` extension must be listed before `sphinx.ext.napoleon`, otherwise it will not work.
:::
