from .core import Pooch as Pooch
from .core import create as create
from .typing import Processor

class Unzip:
    def __init__(self, extract_dir: str | None = None) -> None: ...
    def __call__(self, fname: str, action: str | None, pooch: Pooch | None) -> object: ...

_u: Processor = Unzip()  # type assertion
