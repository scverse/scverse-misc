"""Reusable, declarative dataset download for scverse packages.

Parse a YAML registry into typed :class:`DatasetEntry` objects, then download and load
one with :func:`fetch`. Dataset ``type`` strings are dispatched against a pluggable loader
registry (:func:`register_loader`); ``anndata`` and ``spatialdata`` loaders ship built in.

Requires the ``datasets`` extra (``pip install scverse-misc[datasets]``); the built-in
``spatialdata`` loader additionally needs the ``spatialdata`` extra.
"""

from __future__ import annotations

from ._fetcher import Download, Loader, available_loaders, fetch, register_loader
from ._registry import DatasetEntry, FileEntry, parse_registry

__all__ = [
    "FileEntry",
    "DatasetEntry",
    "parse_registry",
    "fetch",
    "register_loader",
    "available_loaders",
    "Loader",
    "Download",
]
