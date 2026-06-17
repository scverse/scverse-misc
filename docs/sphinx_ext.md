```{toctree}
:hidden: true
:maxdepth: 10
```

# Sphinx extension
This package provides a Sphinx extension to create or adjust documentation.
For example, using the [deprecated decorator](#scverse_misc.deprecated) adds a deprecation notice to the function's description.
To use the extension, add `"scverse_misc.sphinx_ext"` to your extensions array in `conf.py`.
The extension requires `scverse_misc` to be installed with the `sphinx` extra.

:::{important}
The `scverse_misc.sphinx_ext` extension must be listed before `sphinx.ext.napoleon`, otherwise it will not work.
:::

# Examples

## Deprecating a function

### source

```{eval-rst}
.. literalinclude:: sphinx_ext_examples/deprecated_decorator.py
   :language: python
```

### rendered

```{eval-rst}
.. autofunction:: deprecated_decorator.foo
```

## Deprecating a function argument

### source

```{eval-rst}
.. literalinclude:: sphinx_ext_examples/deprecated_arg.py
   :language: python
```

### rendered

```{eval-rst}
.. autofunction:: deprecated_arg.foo
```

## Settings class

### source

```{eval-rst}
.. literalinclude:: sphinx_ext_examples/package.py
   :language: python
```

### rendered

```{eval-rst}
.. autodata:: package.settings

.. autofunction:: package.settings.override
```
