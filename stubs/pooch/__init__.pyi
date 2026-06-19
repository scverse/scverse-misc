from .typing import Downloader, PathInputType, PathType, Processor

def create(
    path: PathInputType,
    base_url: str,
    version: str | None = None,
    version_dev: str = "master",
    env: str | None = None,
    registry: dict[str, str | None] | None = None,
    urls: dict[str, str] | None = None,
    retry_if_failed: int = 0,
    allow_updates: bool | str = True,
) -> Pooch: ...

class Pooch:
    def __init__(
        self,
        path: PathType,
        base_url: str,
        registry: dict[str, str | None] | None = None,
        urls: dict[str, str] | None = None,
        retry_if_failed: int = 0,
        allow_updates: bool = True,
    ) -> None: ...
    def fetch(
        self,
        fname: str,
        processor: Processor | None = None,
        downloader: Downloader | None = None,
        progressbar: bool = False,
    ) -> str: ...

class Unzip:
    def __init__(self, extract_dir: str | None = None) -> None: ...
    def __call__(self, fname: str, action: str | None, pooch: Pooch | None) -> object: ...

_u: Processor = Unzip()  # type assertion
