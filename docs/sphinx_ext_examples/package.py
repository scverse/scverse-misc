from typing import Annotated

from scverse_misc import Settings
from pydantic import Field


class _Settings(Settings):
    frobnicate: bool = False
    """Controls whether to frobnicate."""

    eps: Annotated[float, Field(gt=0, lt=1)] = 1e-8
    """Small epsilon for numerical stability"""


settings = _Settings()
