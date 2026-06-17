# API

```{eval-rst}
.. currentmodule:: scverse_misc
.. toctree::
```

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

## Deprecations
```{eval-rst}
.. autosummary::
   :toctree: generated

   deprecated
   deprecated_arg
   Deprecation
```

## Datasets

Reusable dataset registry + downloader (requires the `datasets` extra).

```{eval-rst}
.. currentmodule:: scverse_misc.datasets
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

## Settings

```{eval-rst}
.. toctree::
   :hidden:

   api/settings

+---------------------------+----------------------------------+
| :class:`Settings` ()      | Base class for package settings. |
+---------------------------+----------------------------------+
```
