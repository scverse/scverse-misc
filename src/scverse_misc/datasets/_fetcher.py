"""Download + load a dataset: a thin ``fetch`` over pooch + a pluggable ``type -> loader`` registry.

A loader is a callable ``(entry, target_dir, download, **kwargs) -> object`` where ``download``
is ``(FileEntry, dest=None, processor=None) -> path`` (pooch under the hood: hashing, caching,
retries, and archive processors). ``anndata`` and ``spatialdata`` loaders ship built in.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast, overload

if TYPE_CHECKING:
    from anndata import AnnData
    from pooch.typing import Processor
    from spatialdata import SpatialData

    from ._registry import DatasetEntry, FileEntry


__all__ = ["register_loader", "available_loaders", "fetch", "Loader", "DownloadCB"]


class Loader[T](Protocol):
    """Function that can be annotated by :func:`register_loader`."""

    def __call__(self, entry: DatasetEntry, target: Path, download: DownloadCB, /, **kwargs: object) -> T: ...


class DownloadCB(Protocol):
    """Callback passed as `download` to a :class:`Loader`."""

    def __call__(self, file: FileEntry, /, *, dest: Path | None = None, processor: Processor | None = None) -> str: ...


_LOADERS: dict[str, Loader[object]] = {}


@overload
def register_loader[T](type_name: str) -> Callable[[Loader[T]], Loader[T]]: ...
@overload
def register_loader[T](type_name: str, loader: Loader[T]) -> Loader[T]: ...
def register_loader[T](type_name: str, loader: Loader[T] | None = None) -> Callable[[Loader[T]], Loader[T]] | Loader[T]:
    """Register a loader for a dataset ``type`` (decorator or direct call)."""

    def deco(fn: Loader[T]) -> Loader[T]:
        _LOADERS[type_name] = fn
        return fn

    return deco if loader is None else deco(loader)


def available_loaders() -> list[str]:
    """Return the names of all registered loader types."""
    return sorted(_LOADERS)


def fetch[T](
    entry: DatasetEntry, cache_dir: str | Path, *, base_url: str | None = None, retries: int = 3, **kwargs: object
) -> T:  # type: ignore[type-var]
    """Download (if needed) and load ``entry``, dispatching to the loader registered for ``entry.type``.

    Files are cached under ``cache_dir / entry.type``. ``kwargs`` are passed to the loader.
    """
    target = Path(cache_dir) / entry.type

    def download(file: FileEntry, /, dest: Path | None = None, processor: Processor | None = None) -> str:
        import pooch

        out = dest or target
        out.mkdir(parents=True, exist_ok=True)
        pup = pooch.create(
            path=str(out),
            base_url="",
            registry={file.name: f"sha256:{file.sha256}" if file.sha256 else None},
            urls={file.name: file.resolve_url(base_url)},
            retry_if_failed=retries,
        )
        return pup.fetch(file.name, processor=processor, progressbar=True)

    if entry.type not in _LOADERS:
        raise KeyError(f"No loader registered for type {entry.type!r}. Available: {available_loaders()}")
    return cast("Loader[T]", _LOADERS[entry.type])(entry, target, download, **kwargs)


@register_loader("anndata")
def _load_anndata(entry: DatasetEntry, target: Path, download: DownloadCB, /, **kwargs: object) -> AnnData:
    """Built-in loader: download a single ``.h5ad`` and read it with :func:`anndata.read_h5ad`."""
    import anndata

    return anndata.read_h5ad(download(entry.file(suffix=".h5ad")), **cast("dict[str, Any]", kwargs))


@register_loader("spatialdata")
def _load_spatialdata(entry: DatasetEntry, target: Path, download: DownloadCB, /, **kwargs: object) -> SpatialData:
    """Built-in loader: download a ``.zip``, unzip it (via pooch) to ``<name>.zarr`` and read it.

    Needs the ``spatialdata`` extra.
    """
    import pooch
    import spatialdata as sd

    download(entry.file(suffix=".zip"), processor=pooch.Unzip(extract_dir="."))
    zarr_path = target / f"{entry.name}.zarr"
    if not zarr_path.exists():
        raise RuntimeError(f"Expected extracted data at {zarr_path}, but it was not found.")
    return sd.read_zarr(zarr_path, **cast("dict[str, Any]", kwargs))
