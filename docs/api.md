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

*Examples:* {ref}`example-extension-namespaces`

(deprecations)=
## Deprecations

```{eval-rst}
.. autosummary::
   :toctree: generated

   deprecated
   deprecated_arg
   Deprecation
```

*Examples:* {ref}`example-deprecating-a-function`, {ref}`example-deprecating-a-function-argument`, {ref}`example-settings-class`

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

*Examples:* {ref}`example-settings-class`

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
