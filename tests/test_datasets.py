from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import pytest

from scverse_misc.datasets import (
    DatasetRegistry,
    FetchContext,
    Fetcher,
    FileEntry,
    available_loaders,
    get_loader,
    register_loader,
)

if TYPE_CHECKING:
    from pathlib import Path

_YAML = """\
base_url: https://example.org/data/
datasets:
  toy:
    type: dummy
    doc_header: A toy dataset.
    metadata:
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
def registry(tmp_path: Path) -> DatasetRegistry:
    p = tmp_path / "datasets.yaml"
    p.write_text(_YAML)
    return DatasetRegistry.from_yaml(p)


def test_from_yaml(registry: DatasetRegistry) -> None:
    assert registry.base_url == "https://example.org/data/"
    assert set(registry) == {"toy", "remote"}
    toy = registry["toy"]
    assert toy.type == "dummy"
    assert toy.doc_header == "A toy dataset."
    assert toy.metadata["shape"] == [10, 3]
    assert toy.file(suffix=".h5ad").sha256 == "abc123"


def test_unknown_dataset(registry: DatasetRegistry) -> None:
    assert "nope" not in registry
    with pytest.raises(KeyError, match="Unknown dataset"):
        registry["nope"]


def test_file_urls() -> None:
    # url wins and comes first, then base_url/s3_key
    f = FileEntry(name="x.zip", url="https://z/x.zip", s3_key="x.zip")
    assert f.urls("https://b/") == ["https://z/x.zip", "https://b/x.zip"]
    # s3_key only needs a base_url
    assert FileEntry(name="x", s3_key="k").urls("https://b") == ["https://b/k"]
    # neither resolvable -> error
    with pytest.raises(ValueError, match="neither"):
        FileEntry(name="x", s3_key="k").urls(None)


def test_file_selection_is_unambiguous(registry: DatasetRegistry) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        registry["toy"].file(suffix=".missing")
    with pytest.raises(ValueError, match="exactly one of"):
        registry["toy"].file()


def test_builtin_loaders_are_shipped() -> None:
    assert {"anndata", "spatialdata"} <= set(available_loaders())


def test_register_and_dispatch(registry: DatasetRegistry, tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    @register_loader("dummy")
    def _load(ctx: FetchContext, /, **kw: object) -> str:
        seen.update(kw)
        return ctx.entry.name

    try:
        # explicit cache_dir avoids importing pooch; dummy loader does no download
        fetched = Fetcher(registry, cache_dir=tmp_path).fetch("toy", foo=1)
        assert fetched == "toy"
        assert seen == {"foo": 1}
        assert get_loader("dummy") is _load
    finally:
        from scverse_misc.datasets import _fetcher

        _fetcher._LOADERS.pop("dummy", None)


def test_unknown_loader(registry: DatasetRegistry, tmp_path: Path) -> None:
    # "toy" is type "dummy" but no dummy loader registered here
    with pytest.raises(KeyError, match="No loader registered"):
        Fetcher(registry, cache_dir=tmp_path).fetch("toy")


def test_extract_archive(registry: DatasetRegistry, tmp_path: Path) -> None:
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("inner/data.txt", "hello")
    ctx = FetchContext(registry["toy"], tmp_path, base_url=None)
    out = ctx.extract_archive(archive, tmp_path / "out")
    assert (out / "inner" / "data.txt").read_text() == "hello"
