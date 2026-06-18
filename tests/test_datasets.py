from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from scverse_misc.datasets import (
    DatasetEntry,
    FileEntry,
    _fetcher,
    available_loaders,
    fetch,
    parse_registry,
    register_loader,
)

if TYPE_CHECKING:
    from scverse_misc.datasets import DownloadCB


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


def test_parse_registry_tolerates_extra_file_keys(tmp_path: Path) -> None:
    p = tmp_path / "datasets.yaml"
    p.write_text(
        "datasets:\n"
        "  d:\n"
        "    type: dummy\n"
        "    files:\n"
        "      - name: x.h5ad\n"
        "        url: https://z/x.h5ad\n"
        "        description: an unknown-to-FileEntry key\n"
    )
    _, datasets = parse_registry(p)  # must not raise on the extra `description` key
    assert datasets["d"].file(name="x.h5ad").url == "https://z/x.h5ad"


def test_resolve_url() -> None:
    # explicit url takes precedence over s3_key
    assert FileEntry(name="x.zip", url="https://z/x.zip", s3_key="x.zip").resolve_url("https://b/") == "https://z/x.zip"
    # s3_key resolves against base_url
    assert FileEntry(name="x", s3_key="k").resolve_url("https://b") == "https://b/k"
    # neither resolvable -> error
    with pytest.raises(ValueError, match="neither"):
        FileEntry(name="x", s3_key="k").resolve_url(None)


def test_file_selection_is_unambiguous(registry: dict[str, DatasetEntry]) -> None:
    assert registry["toy"].file(name="toy.h5ad").s3_key == "toy.h5ad"  # exact name match
    with pytest.raises(ValueError, match="exactly one"):
        registry["toy"].file(name="nope.h5ad")
    with pytest.raises(ValueError, match="exactly one"):
        registry["toy"].file(suffix=".missing")
    with pytest.raises(ValueError, match="exactly one of"):
        registry["toy"].file()


def test_builtin_loaders_are_shipped() -> None:
    assert {"anndata", "spatialdata"} <= set(available_loaders())


def test_register_and_dispatch(registry: dict[str, DatasetEntry], tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    @register_loader("dummy")
    def _load(entry: DatasetEntry, target: Path, download: DownloadCB, /, **kw: object) -> str:
        seen.update(kw)
        return entry.name

    try:
        # dummy loader does no download, so no network / pooch needed
        assert fetch(registry["toy"], tmp_path, base_url="https://b", foo=1) == "toy"
        assert seen == {"foo": 1}
    finally:
        _fetcher._LOADERS.pop("dummy", None)


def test_unknown_loader(registry: dict[str, DatasetEntry], tmp_path: Path) -> None:
    # "toy" is type "dummy" but no dummy loader registered here
    with pytest.raises(KeyError, match="No loader registered"):
        fetch(registry["toy"], tmp_path)


def test_download_drives_pooch(
    registry: dict[str, DatasetEntry], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `download` closure wires FileEntry -> pooch.create/fetch without touching the network."""
    calls: dict[str, object] = {}

    class FakePup:
        def fetch(self, name: str, *, processor: object, progressbar: bool) -> str:
            calls["fetched"] = name
            calls["processor"] = processor
            return f"/cache/{name}"

    def fake_create(**kw: object) -> FakePup:
        calls.update(kw)
        return FakePup()

    import pooch

    monkeypatch.setattr(pooch, "create", fake_create)

    @register_loader("dummy")
    def _load(entry: DatasetEntry, target: Path, download: DownloadCB, /, **kw: object) -> str:
        return download(entry.file(suffix=".h5ad"))

    try:
        assert fetch(registry["toy"], tmp_path, base_url="https://b") == "/cache/toy.h5ad"
    finally:
        _fetcher._LOADERS.pop("dummy", None)

    assert calls["urls"] == {"toy.h5ad": "https://b/toy.h5ad"}
    assert calls["registry"] == {"toy.h5ad": "sha256:abc123"}
    assert calls["fetched"] == "toy.h5ad"


# old anndata versions use the old argument
@pytest.mark.filterwarnings(r"ignore:The (decorator_name|docstring_style) argument is deprecated:DeprecationWarning")
def test_load_anndata_reads_h5ad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import anndata

    monkeypatch.setattr(anndata, "read_h5ad", lambda path, **kw: ("adata", path, kw))
    entry = DatasetEntry(name="toy", type="anndata", files=(FileEntry(name="toy.h5ad", url="https://z/toy.h5ad"),))
    result: object = _fetcher._load_anndata(entry, tmp_path, lambda f, **kw: "/cache/toy.h5ad", backed="r")
    assert result == ("adata", "/cache/toy.h5ad", {"backed": "r"})


def test_load_spatialdata_reads_zarr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_sd = types.ModuleType("spatialdata")
    fake_sd.read_zarr = lambda path, **kw: ("sdata", path)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "spatialdata", fake_sd)
    entry = DatasetEntry(
        name="cells", type="spatialdata", files=(FileEntry(name="cells.zip", url="https://z/cells.zip"),)
    )

    # download extracted nothing -> loud failure (0 zarrs found)
    with pytest.raises(RuntimeError, match="Expected exactly one"):
        _fetcher._load_spatialdata(entry, tmp_path, lambda f, **kw: str(kw["dest"]))

    # the extracted .zarr need not be named after the registry key; glob finds the single one
    def extract(file: FileEntry, **kw: object) -> str:
        dest = kw["dest"]
        assert isinstance(dest, Path)
        (dest / "whatever.zarr").mkdir(parents=True)
        return str(dest)

    result: object = _fetcher._load_spatialdata(entry, tmp_path, extract)
    assert result == ("sdata", tmp_path / "cells" / "whatever.zarr")
