```{toctree}
:hidden: true
:maxdepth: 10
```

# Sphinx extension
This package provides a Sphinx extension to create or adjust documentation.
For example, using the [deprecated decorator](#scverse_misc.deprecated) adds a deprecation notice to the function's description.
To use the extension, add `"scverse_misc.sphinx_ext"` to your extensions array in `conf.py`.
The extension requires `scverse_misc` to be installed with the `sphinx` extra.

The extension also ships and enables several templates for `sphinx.ext.autosummary`.
These were previously part of the [scverse cookiecutter template](https://github.com/scverse/cookiecutter-scverse).
This keeps the cookiecutter template lean and ensures that scverse packages have a consistent documentation design, even if some packages are not updating the cookiecutter template.
If you have custom autosummary templates in your package, they will still be used.

# Examples

(example-deprecating-a-function)=
## Deprecating a function

### source

```{literalinclude} sphinx_ext_examples/deprecated_decorator.py
:language: python
```

### rendered

```{eval-rst}
.. autofunction:: deprecated_decorator.foo
```

(example-deprecating-a-function-argument)=
## Deprecating a function argument

### source

```{literalinclude} sphinx_ext_examples/deprecated_arg.py
:language: python
```

### rendered

```{eval-rst}
.. autofunction:: deprecated_arg.foo
```

(example-settings-class)=
## Settings class

### source

```{literalinclude} sphinx_ext_examples/package.py
:language: python
```

### rendered

```{eval-rst}
.. autodata:: package.settings

.. autofunction:: package.settings.override
.. autofunction:: package.settings.reset
```

(example-extension-namespaces)=
## Extension namespaces

### source

```{literalinclude} sphinx_ext_examples/extension.py
:language: python
```

### rendered

```{eval-rst}
.. autoclass:: extension.DummyClass
.. autodecorator:: extension.register_namespace
```
