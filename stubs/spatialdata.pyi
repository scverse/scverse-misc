import os
from typing import Any

class SpatialData: ...

def read_zarr(path: str | os.PathLike[str], **kwargs: Any) -> SpatialData: ...  # noqa: ANN401
