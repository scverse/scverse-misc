from typing import Annotated

from scverse_misc import Settings, deprecated, Deprecation
from pydantic import Field


class _Settings(Settings):
    frobnicate: bool = False
    """Controls whether to frobnicate."""

    eps: Annotated[
        float,
        Field(gt=0, lt=1, deprecated=deprecated(Deprecation("0.4.2", "This functionality does not exist anymore."))),
    ] = 1e-8
    """Small epsilon for numerical stability"""


settings = _Settings()
