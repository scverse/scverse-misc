import os
from collections.abc import Callable
from typing import Literal, Protocol

from .core import Pooch

type Action = Literal["download", "fetch", "update"]
type PathType = str | os.PathLike[str]
type PathInputType = PathType | list[PathType] | tuple[PathType, ...]
type Processor = Callable[[str, Action, Pooch | None], object]

class Downloader(Protocol):
    def __call__(  # noqa: E704
        self,
        fname: str,
        action: PathType | None,
        pooch: Pooch | None,
        *,
        check_only: bool | None = None,
    ) -> object: ...
