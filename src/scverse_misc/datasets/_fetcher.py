"""Download + load datasets: pooch fetch with hash verification, plus a pluggable loader registry."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, overload

from ._registry import DatasetRegistry

if TYPE_CHECKING:
    from collections.abc import Callable

    from ._registry import DatasetEntry, FileEntry

__all__ = ["Loader", "FetchContext", "Fetcher", "register_loader", "get_loader", "available_loaders"]

logger = logging.getLogger("scverse_misc.datasets")


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
    """Handed to a loader: the dataset entry plus download/extract helpers.

    Loaders should use :meth:`download` / :meth:`download_all` / :meth:`extract_archive`
    rather than re-implementing fetching, so hashing and caching stay consistent.
    """

    def __init__(self, entry: DatasetEntry, target_dir: Path, base_url: str | None) -> None:
        self.entry = entry
        self.target_dir = target_dir
        self._base_url = base_url

    def download(self, file: FileEntry, dest: Path | None = None) -> Path:
        """Download a single file (cached, hash-verified) into ``dest`` (default: ``target_dir``)."""
        target = dest or self.target_dir
        target.mkdir(parents=True, exist_ok=True)
        local = target / file.name
        if local.exists():
            logger.debug("Using cached file %s", local)
            return local

        import pooch

        errors: list[Exception] = []
        for url in file.urls(self._base_url):
            try:
                logger.info("Downloading %s from %s", file.name, url)
                got = pooch.retrieve(
                    url=url,
                    known_hash=f"sha256:{file.sha256}" if file.sha256 else None,
                    fname=file.name,
                    path=str(target),
                    progressbar=True,
                )
                return Path(got)
            except (OSError, ValueError, RuntimeError) as e:
                logger.warning("Failed to download from %s: %s", url, e)
                errors.append(e)
        raise ExceptionGroup(f"Failed to download {file.name}", errors)

    def download_all(self, dest: Path | None = None) -> list[Path]:
        """Download every file in the dataset and return their local paths."""
        return [self.download(f, dest) for f in self.entry.files]

    def extract_archive(self, archive: Path, dest: Path | None = None) -> Path:
        """Unpack a ``.zip``/``.tar.*`` archive into ``dest`` (default: the archive's directory)."""
        dest = dest or archive.parent
        dest.mkdir(parents=True, exist_ok=True)
        shutil.unpack_archive(str(archive), str(dest))
        return dest


class Fetcher:
    """Download and load datasets from a :class:`DatasetRegistry`.

    Parameters
    ----------
    registry
        The dataset registry, or a path to a YAML file to load it from.
    cache_dir
        Base directory for downloads. Defaults to a platform cache dir via :func:`pooch.os_cache`.
        Each dataset is stored under ``cache_dir / <type>``.
    """

    def __init__(self, registry: DatasetRegistry | str, cache_dir: Path | str | None = None) -> None:
        self.registry = registry if isinstance(registry, DatasetRegistry) else DatasetRegistry.from_yaml(registry)
        if cache_dir is None:
            import pooch

            cache_dir = pooch.os_cache("scverse_misc")
        self.cache_dir = Path(cache_dir)

    def fetch(self, name: str, **kwargs: Any) -> Any:
        """Download (if needed) and load the dataset ``name``, passing ``kwargs`` to its loader."""
        entry = self.registry[name]
        loader = get_loader(entry.type)
        ctx = FetchContext(entry, self.cache_dir / entry.type, self.registry.base_url)
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
    import spatialdata as sd

    zarr_path = ctx.target_dir / f"{ctx.entry.name}.zarr"
    if not zarr_path.exists():
        zip_path = ctx.download(ctx.entry.file(suffix=".zip"))
        ctx.extract_archive(zip_path)
        if not zarr_path.exists():
            raise RuntimeError(f"Expected extracted data at {zarr_path}, but it was not found.")
    return sd.read_zarr(zarr_path, **kwargs)
