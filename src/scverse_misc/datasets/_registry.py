"""Declarative registry of downloadable datasets, loaded from YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from os import PathLike

__all__ = ["FileEntry", "DatasetEntry", "DatasetRegistry"]


@dataclass(frozen=True, slots=True)
class FileEntry:
    """A single downloadable file belonging to a dataset.

    Parameters
    ----------
    name
        File name as it should appear on disk (e.g. ``"cells.zip"``).
    url
        Full download URL (e.g. a Zenodo file URL). Tried first if set.
    s3_key
        Key relative to the registry's ``base_url``. Tried after ``url``.
    sha256
        Expected SHA-256 hash. If set, downloads are verified against it.
    """

    name: str
    url: str | None = None
    s3_key: str | None = None
    sha256: str | None = None

    def urls(self, base_url: str | None = None) -> list[str]:
        """Return candidate URLs to try, in order (``url`` first, then ``base_url/s3_key``)."""
        out: list[str] = []
        if self.url:
            out.append(self.url)
        if base_url and self.s3_key:
            out.append(f"{base_url.rstrip('/')}/{self.s3_key}")
        if not out:
            raise ValueError(f"FileEntry {self.name!r} has neither `url` nor `s3_key` (with a registry `base_url`).")
        return out


@dataclass(frozen=True, slots=True)
class DatasetEntry:
    """A named dataset made up of one or more files.

    Parameters
    ----------
    name
        Dataset name (the registry key).
    type
        Loader type, dispatched against the loader registry (e.g. ``"anndata"``, ``"spatialdata"``).
    files
        The files that make up the dataset.
    doc_header
        Optional one-line description.
    metadata
        Free-form extra metadata (shape, library_id, ...). Not interpreted by the core.
    """

    name: str
    type: str
    files: tuple[FileEntry, ...]
    doc_header: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def file(self, *, name: str | None = None, suffix: str | None = None) -> FileEntry:
        """Return the file matching ``name`` (exact) or ``suffix`` (endswith). Raises if not exactly one matches."""
        if (name is None) == (suffix is None):
            raise ValueError("Pass exactly one of `name` or `suffix`.")
        if name is not None:
            matches = [f for f in self.files if f.name == name]
            crit = f"name={name!r}"
        else:
            assert suffix is not None
            matches = [f for f in self.files if f.name.endswith(suffix)]
            crit = f"suffix={suffix!r}"
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one file with {crit} in {self.name!r}, found {len(matches)}.")
        return matches[0]


@dataclass(frozen=True, slots=True)
class DatasetRegistry:
    """A collection of :class:`DatasetEntry` with an optional shared ``base_url``."""

    base_url: str | None = None
    datasets: Mapping[str, DatasetEntry] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: PathLike[str] | str) -> DatasetRegistry:
        """Build a registry from a YAML file.

        The YAML has a top-level ``base_url`` (or ``s3_base_url``) and a ``datasets`` mapping of
        ``name -> {type, doc_header?, metadata?, files: [{name, url?/s3_key?, sha256?}]}``.
        """
        with open(path) as f:
            config = yaml.safe_load(f) or {}
        base_url = config.get("base_url") or config.get("s3_base_url")
        datasets: dict[str, DatasetEntry] = {}
        for name, data in (config.get("datasets") or {}).items():
            files = tuple(
                FileEntry(
                    name=fd["name"],
                    url=fd.get("url"),
                    s3_key=fd.get("s3_key"),
                    sha256=fd.get("sha256"),
                )
                for fd in data.get("files", [])
            )
            datasets[name] = DatasetEntry(
                name=name,
                type=data["type"],
                files=files,
                doc_header=data.get("doc_header"),
                metadata=data.get("metadata", {}),
            )
        return cls(base_url=base_url, datasets=datasets)

    def __getitem__(self, name: str) -> DatasetEntry:
        if name not in self.datasets:
            raise KeyError(f"Unknown dataset {name!r}. Available: {sorted(self.datasets)}")
        return self.datasets[name]

    def __contains__(self, name: object) -> bool:
        return name in self.datasets

    def __iter__(self) -> Iterator[str]:
        return iter(self.datasets)
