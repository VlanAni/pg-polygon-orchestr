from abc import ABC, abstractmethod

import typing


class Serializable(ABC):

    @abstractmethod
    def serialize(self) -> typing.Mapping[str, typing.Any]:
        pass
