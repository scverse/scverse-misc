"""Reusable, declarative dataset registry + downloader for scverse packages.

Define datasets in a YAML registry, then download and load them through a
:class:`Fetcher`. Dataset ``type`` strings are dispatched against a pluggable
loader registry (:func:`register_loader`); ``anndata`` and ``spatialdata``
loaders ship built in.

Requires the ``datasets`` extra (``pip install scverse-misc[datasets]``); the
built-in ``spatialdata`` loader additionally needs the ``spatialdata`` extra.
"""

from __future__ import annotations

from ._fetcher import (
    FetchContext,
    Fetcher,
    Loader,
    available_loaders,
    get_loader,
    register_loader,
)
from ._registry import DatasetEntry, DatasetRegistry, FileEntry

__all__ = [
    "DatasetRegistry",
    "DatasetEntry",
    "FileEntry",
    "Fetcher",
    "FetchContext",
    "Loader",
    "register_loader",
    "get_loader",
    "available_loaders",
]
