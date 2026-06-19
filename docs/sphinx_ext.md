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

(example-deprecating-a-function)=
## Deprecating a function

*API:* {class}`~scverse_misc.deprecated`, {class}`~scverse_misc.Deprecation`

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

*API:* {class}`~scverse_misc.deprecated_arg`, {class}`~scverse_misc.Deprecation`

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

*API:* {class}`~scverse_misc.Settings`, {class}`~scverse_misc.deprecated`, {class}`~scverse_misc.Deprecation`

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

*API:* {func}`~scverse_misc.make_register_namespace_decorator`, {class}`~scverse_misc.ExtensionNamespace`

### source

```{literalinclude} sphinx_ext_examples/extension.py
:language: python
```

### rendered

```{eval-rst}
.. autoclass:: extension.DummyClass
.. autodecorator:: extension.register_namespace
```
