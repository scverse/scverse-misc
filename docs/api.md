# API

```{eval-rst}
.. module:: scverse_misc
.. toctree::
```

(extensions)=
## Extensions

```{eval-rst}
.. autosummary::
    :toctree: generated

    make_register_namespace_decorator
```

Types used by the former:

```{eval-rst}
.. autosummary::
    :toctree: generated

    ExtensionNamespace
```

_Examples:_ {ref}`example-extension-namespaces`

(deprecations)=
## Deprecations

```{eval-rst}
.. autosummary::
   :toctree: generated

   deprecated
   deprecated_arg
   future_abstractmethod
   Deprecation
```

_Examples:_ {ref}`example-deprecating-a-function`, {ref}`example-deprecating-a-function-argument`, {ref}`example-settings-class`

(settings)=
## Settings

```{eval-rst}
.. toctree::
   :hidden:

   api/settings

.. autosummary::
   :signatures: short

   Settings
```

_Examples:_ {ref}`example-settings-class`

(arg_alias)=
## Argument value aliasing

```{eval-rst}
.. autosummary::
   :toctree: generated

    arg_alias
```

(logging)=
## Logging (`scverse_misc.logging`)

```{eval-rst}
.. automodule:: scverse_misc.logging
.. autosummary::
    :toctree: generated

    get_logger
    TimedLogger
```

Configuration:

```{eval-rst}
.. toctree::
   :hidden:

   api/logging-config

.. autosummary::

   config
```

(datasets)=
## Datasets (`scverse_misc.datasets`)

```{eval-rst}
.. automodule:: scverse_misc.datasets
.. autosummary::
    :toctree: generated

    DatasetEntry
    FileEntry
    parse_registry
    fetch
    register_loader
    available_loaders
    Loader
    DownloadCB
```
