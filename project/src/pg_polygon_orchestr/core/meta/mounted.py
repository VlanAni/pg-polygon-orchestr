from abc import ABC, abstractmethod
from enum import Enum


class MountableType(Enum):
    VOLUME = 1
    HOSTPATH = 2


class Mountable(ABC):

    @abstractmethod
    def source(self) -> str:
        pass

    @abstractmethod
    def mtype(self) -> MountableType:
        pass
