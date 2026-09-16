from abc import abstractmethod
import typing
from ..serializable import Serializable


class Step(Serializable):

    @abstractmethod
    def perform(self) -> None | typing.Any:
        pass
