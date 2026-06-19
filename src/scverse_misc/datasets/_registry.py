"""Typed dataset entries + a YAML parser. Plain data — no registry/fetcher machinery."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from collections.abc import Mapping
    from os import PathLike

__all__ = ["FileEntry", "DatasetEntry", "parse_registry"]


@dataclass(frozen=True, slots=True)
class FileEntry:
    """A single downloadable file belonging to a dataset.

    Parameters
    ----------
    name
        File name as it should appear on disk (e.g. ``"cells.zip"``).
    url
        Full download URL (e.g. a Zenodo file URL). Takes precedence over ``s3_key``.
    s3_key
        Key relative to the registry's ``base_url``. Used when ``url`` is unset.
    sha256
        Expected SHA-256 hash. If set, downloads are verified against it.
    """

    name: str
    url: str | None = None
    s3_key: str | None = None
    sha256: str | None = None

    def resolve_url(self, base_url: str | None = None) -> str:
        """Resolve the download URL: the explicit ``url`` if set, else ``base_url/s3_key``."""
        if self.url:
            return self.url
        if base_url and self.s3_key:
            return f"{base_url.rstrip('/')}/{self.s3_key}"
        raise ValueError(f"FileEntry {self.name!r} has neither `url` nor `s3_key` (with a registry `base_url`).")


@dataclass(frozen=True, slots=True)
class DatasetEntry:
    """A named dataset made up of one or more files.

    ``metadata`` holds everything in the YAML row other than ``type`` and ``files``
    (e.g. ``shape``, ``library_id``, ``doc_header``); the core does not interpret it.
    """

    name: str
    type: str
    files: tuple[FileEntry, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def file(self, *, name: str | None = None, suffix: str | None = None) -> FileEntry:
        """Return the file matching ``name`` (exact) or ``suffix`` (endswith). Raises unless exactly one matches."""
        if name is not None:
            matches = [f for f in self.files if f.name == name]
            crit = f"name={name!r}"
        elif suffix is not None:
            matches = [f for f in self.files if f.name.endswith(suffix)]
            crit = f"suffix={suffix!r}"
        else:
            raise ValueError("Pass exactly one of `name` or `suffix`.")
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one file with {crit} in {self.name!r}, found {len(matches)}.")
        return matches[0]


_FILE_FIELDS = frozenset(f.name for f in fields(FileEntry))


def _file_entry(fd: Mapping[str, Any], dataset: str) -> FileEntry:
    """Build a :class:`FileEntry`, warning on (and dropping) keys it doesn't recognise.

    Unknown keys are tolerated so per-file extras (e.g. ``description``) don't crash the
    parse, but a warning surfaces likely typos.
    """
    if unknown := fd.keys() - _FILE_FIELDS:
        warnings.warn(f"Ignoring unknown file keys {sorted(unknown)} in dataset {dataset!r}.", stacklevel=3)
    return FileEntry(**{k: v for k, v in fd.items() if k in _FILE_FIELDS})


def parse_registry(path: PathLike[str] | str) -> tuple[str | None, dict[str, DatasetEntry]]:
    """Parse a YAML registry into ``(base_url, {name: DatasetEntry})``.

    The YAML has a top-level ``base_url`` (or ``s3_base_url``) and a ``datasets`` mapping of
    ``name -> {type, files: [{name, url?/s3_key?, sha256?}], ...}``. Any keys other than ``type``
    and ``files`` are collected into the entry's ``metadata``.
    """
    with open(path) as f:
        config = yaml.safe_load(f) or {}
    base_url = config.get("base_url") or config.get("s3_base_url")
    datasets = {
        name: DatasetEntry(
            name=name,
            type=row["type"],
            files=tuple(_file_entry(fd, name) for fd in row.get("files", [])),
            metadata={k: v for k, v in row.items() if k not in ("type", "files")},
        )
        for name, row in (config.get("datasets") or {}).items()
    }
    return base_url, datasets
