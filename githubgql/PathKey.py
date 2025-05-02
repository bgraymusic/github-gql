from __future__ import annotations
from typing import Any, Iterable, overload


class PathKey(list[str]):
    """A list of strings that can be used as a dictionary key"""

    def __init__(self, iterable: Iterable[str] = []):
        super().__init__(iterable)

    def copy(self):
        return PathKey(super().copy())

    def __hash__(self):
        return hash("/".join(self))

    def __eq__(self, value: Any):
        return (isinstance(value, PathKey) or isinstance(value, list)) and "/".join(self) == "/".join(value)
