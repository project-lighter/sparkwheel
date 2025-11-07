import os
from typing import Union

__all__ = ["PathLike"]

PathLike = Union[str, os.PathLike]
