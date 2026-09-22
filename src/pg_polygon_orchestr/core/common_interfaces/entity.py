from abc import abstractmethod

from .infra_object import InfraObject

from ..common_types import InfraType, EntityState, MountConfig, SubnetConfig
from ..serializable import Serializable


class Entity(Serializable, InfraObject):
    """Базовый класс для Volume, Node и Network"""

    @abstractmethod
    def deploy(self, **options: str | list[MountConfig] | list[SubnetConfig]):
        pass

    @abstractmethod
    def clear(self):
        pass

    @abstractmethod
    def remove(self):
        pass

    @property
    @abstractmethod
    def type(self) -> InfraType:
        pass

    @property
    @abstractmethod
    def inf_name(self) -> str:
        pass

    @property
    @abstractmethod
    def real_name(self) -> str:
        pass

    @property
    @abstractmethod
    def state(self) -> EntityState:
        pass
