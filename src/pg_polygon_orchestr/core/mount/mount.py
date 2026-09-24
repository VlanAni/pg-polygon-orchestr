from typing import Any, Mapping, Self

from ..serializable import Serializable, EasyDecodable

import pathlib


class BindMount(Serializable, EasyDecodable):

    def __init__(self, src: str) -> None:
        absolute = pathlib.Path(src).absolute()

        if not absolute.exists():
            raise KeyError(f"the path {absolute} do not exist")

        self.__src = str(absolute)

    @property
    def src(self) -> str:
        return self.__src

    def serialize(self) -> Mapping[str, Any]:
        return {"src": self.__src}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(src=data["src"])
