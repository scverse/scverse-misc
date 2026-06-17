from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from scverse_misc.datasets import (
    DatasetEntry,
    Download,
    FileEntry,
    available_loaders,
    fetch,
    parse_registry,
    register_loader,
)

if TYPE_CHECKING:
    from pathlib import Path

_YAML = """\
base_url: https://example.org/data/
datasets:
  toy:
    type: dummy
    shape: [10, 3]
    files:
      - name: toy.h5ad
        s3_key: toy.h5ad
        sha256: abc123
  remote:
    type: dummy
    files:
      - name: remote.zip
        url: https://zenodo.org/records/1/files/remote.zip
"""


@pytest.fixture
def registry(tmp_path: Path) -> dict[str, DatasetEntry]:
    p = tmp_path / "datasets.yaml"
    p.write_text(_YAML)
    base_url, datasets = parse_registry(p)
    assert base_url == "https://example.org/data/"
    return datasets


def test_parse_registry(registry: dict[str, DatasetEntry]) -> None:
    assert set(registry) == {"toy", "remote"}
    toy = registry["toy"]
    assert toy.type == "dummy"
    assert toy.metadata["shape"] == [10, 3]  # non-type/files keys land in metadata
    assert toy.file(suffix=".h5ad").sha256 == "abc123"


def test_resolve_url() -> None:
    # explicit url takes precedence over s3_key
    assert FileEntry(name="x.zip", url="https://z/x.zip", s3_key="x.zip").resolve_url("https://b/") == "https://z/x.zip"
    # s3_key resolves against base_url
    assert FileEntry(name="x", s3_key="k").resolve_url("https://b") == "https://b/k"
    # neither resolvable -> error
    with pytest.raises(ValueError, match="neither"):
        FileEntry(name="x", s3_key="k").resolve_url(None)


def test_file_selection_is_unambiguous(registry: dict[str, DatasetEntry]) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        registry["toy"].file(suffix=".missing")
    with pytest.raises(ValueError, match="exactly one of"):
        registry["toy"].file()


def test_builtin_loaders_are_shipped() -> None:
    assert {"anndata", "spatialdata"} <= set(available_loaders())


def test_register_and_dispatch(registry: dict[str, DatasetEntry], tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    @register_loader("dummy")
    def _load(entry: DatasetEntry, target: Path, download: Download, /, **kw: object) -> str:
        seen.update(kw)
        return entry.name

    try:
        # dummy loader does no download, so no network / pooch needed
        assert fetch(registry["toy"], tmp_path, base_url="https://b", foo=1) == "toy"
        assert seen == {"foo": 1}
    finally:
        from scverse_misc.datasets import _fetcher

        _fetcher._LOADERS.pop("dummy", None)


def test_unknown_loader(registry: dict[str, DatasetEntry], tmp_path: Path) -> None:
    # "toy" is type "dummy" but no dummy loader registered here
    with pytest.raises(KeyError, match="No loader registered"):
        fetch(registry["toy"], tmp_path)
