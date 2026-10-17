"""Reusable, declarative dataset download for scverse packages.

Parse a YAML registry into typed :class:`DatasetEntry` objects, then download and load
one with :func:`fetch`. Dataset ``type`` strings are dispatched against a pluggable loader
registry (:func:`register_loader`); ``anndata`` and ``spatialdata`` loaders ship built in.

Requires the ``datasets`` extra (``pip install scverse-misc[datasets]``). Each built-in
loader needs its own library at call time: ``spatialdata`` via the ``spatialdata`` extra,
``anndata`` provided by the consumer (scverse-misc does not depend on it).
"""

from __future__ import annotations

from ._fetcher import DownloadCB, Loader, available_loaders, fetch, register_loader
from ._registry import DatasetEntry, FileEntry, parse_registry

__all__ = [
    "FileEntry",
    "DatasetEntry",
    "parse_registry",
    "fetch",
    "register_loader",
    "available_loaders",
    "Loader",
    "DownloadCB",
]
