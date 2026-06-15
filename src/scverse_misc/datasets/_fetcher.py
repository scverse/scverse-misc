"""Download + load datasets: pooch fetch with hash verification, plus a pluggable loader registry."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, overload

from ._registry import DatasetRegistry

if TYPE_CHECKING:
    from collections.abc import Callable

    from ._registry import DatasetEntry, FileEntry

__all__ = ["Loader", "FetchContext", "Fetcher", "register_loader", "get_loader", "available_loaders"]


class Loader(Protocol):
    """A callable that turns a downloaded dataset into an in-memory object."""

    def __call__(self, ctx: FetchContext, /, **kwargs: Any) -> Any: ...


_LOADERS: dict[str, Loader] = {}


@overload
def register_loader(type_name: str) -> Callable[[Loader], Loader]: ...
@overload
def register_loader(type_name: str, loader: Loader) -> Loader: ...
def register_loader(type_name: str, loader: Loader | None = None) -> Callable[[Loader], Loader] | Loader:
    """Register a loader for a dataset ``type``.

    Usable as a decorator (``@register_loader("spatialdata")``) or directly
    (``register_loader("spatialdata", fn)``). The loader receives a :class:`FetchContext`
    and returns the loaded object.
    """

    def decorator(fn: Loader) -> Loader:
        _LOADERS[type_name] = fn
        return fn

    return decorator if loader is None else decorator(loader)


def get_loader(type_name: str) -> Loader:
    """Return the loader registered for ``type_name``, or raise with the available types."""
    if type_name not in _LOADERS:
        raise KeyError(f"No loader registered for type {type_name!r}. Available: {available_loaders()}")
    return _LOADERS[type_name]


def available_loaders() -> list[str]:
    """Return the names of all registered loader types."""
    return sorted(_LOADERS)


class FetchContext:
    """Handed to a loader: the dataset entry plus a pooch-backed download helper.

    Loaders should use :meth:`download` / :meth:`download_all` rather than re-implementing
    fetching, so hashing, caching and retries stay consistent. Pass a pooch ``processor``
    (e.g. :class:`pooch.Unzip`, :class:`pooch.Untar`) to unpack archives.
    """

    def __init__(self, entry: DatasetEntry, target_dir: Path, base_url: str | None, retries: int) -> None:
        self.entry = entry
        self.target_dir = target_dir
        self._base_url = base_url
        self._retries = retries

    def download(self, file: FileEntry, dest: Path | None = None, processor: Any = None) -> Any:
        """Download a file via pooch (cached, hash-verified, retried) into ``dest`` (default: ``target_dir``).

        Returns the local path, or — when a pooch ``processor`` is given — whatever the processor
        returns (e.g. the list of extracted members for :class:`pooch.Unzip`/:class:`pooch.Untar`).
        """
        import pooch

        target = dest or self.target_dir
        target.mkdir(parents=True, exist_ok=True)
        pup = pooch.create(
            path=str(target),
            base_url="",
            registry={file.name: f"sha256:{file.sha256}" if file.sha256 else None},
            urls={file.name: file.urls(self._base_url)[0]},
            retry_if_failed=self._retries,
        )
        return pup.fetch(file.name, processor=processor, progressbar=True)

    def download_all(self, dest: Path | None = None) -> list[Any]:
        """Download every file in the dataset and return their local paths."""
        return [self.download(f, dest) for f in self.entry.files]


class Fetcher:
    """Download and load datasets from a :class:`DatasetRegistry`.

    Parameters
    ----------
    registry
        The dataset registry, or a path to a YAML file to load it from.
    cache_dir
        Base directory for downloads. Defaults to a platform cache dir via :func:`pooch.os_cache`.
        Each dataset is stored under ``cache_dir / <type>``.
    retries
        Number of times pooch retries a failed download (``pooch``'s ``retry_if_failed``).
    """

    def __init__(self, registry: DatasetRegistry | str, cache_dir: Path | str | None = None, retries: int = 3) -> None:
        self.registry = registry if isinstance(registry, DatasetRegistry) else DatasetRegistry.from_yaml(registry)
        if cache_dir is None:
            import pooch

            cache_dir = pooch.os_cache("scverse_misc")
        self.cache_dir = Path(cache_dir)
        self.retries = retries

    def fetch(self, name: str, **kwargs: Any) -> Any:
        """Download (if needed) and load the dataset ``name``, passing ``kwargs`` to its loader."""
        entry = self.registry[name]
        loader = get_loader(entry.type)
        ctx = FetchContext(entry, self.cache_dir / entry.type, self.registry.base_url, self.retries)
        return loader(ctx, **kwargs)


@register_loader("anndata")
def _load_anndata(ctx: FetchContext, /, **kwargs: Any) -> Any:
    """Built-in loader: download a single ``.h5ad`` file and read it with :func:`anndata.read_h5ad`."""
    import anndata

    path = ctx.download(ctx.entry.file(suffix=".h5ad"))
    return anndata.read_h5ad(path, **kwargs)


@register_loader("spatialdata")
def _load_spatialdata(ctx: FetchContext, /, **kwargs: Any) -> Any:
    """Built-in loader: download a ``.zip``, extract it to ``<name>.zarr`` and read it as a SpatialData object.

    Needs the ``spatialdata`` extra.
    """
    import pooch
    import spatialdata as sd

    # pooch's Unzip processor handles extraction + caching; extract_dir="." unpacks into target_dir
    ctx.download(ctx.entry.file(suffix=".zip"), processor=pooch.Unzip(extract_dir="."))
    zarr_path = ctx.target_dir / f"{ctx.entry.name}.zarr"
    if not zarr_path.exists():
        raise RuntimeError(f"Expected extracted data at {zarr_path}, but it was not found.")
    return sd.read_zarr(zarr_path, **kwargs)
