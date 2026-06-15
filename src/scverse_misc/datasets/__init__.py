"""Reusable, declarative dataset registry + downloader for scverse packages.

Define datasets in a YAML registry, then download and load them through a
:class:`Fetcher`. Dataset ``type`` strings are dispatched against a pluggable
loader registry (:func:`register_loader`); an ``anndata`` loader ships built in.

Requires the ``datasets`` extra (``pip install scverse-misc[datasets]``).
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
