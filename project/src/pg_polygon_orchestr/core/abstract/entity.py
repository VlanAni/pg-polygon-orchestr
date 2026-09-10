from abc import ABC, abstractmethod
from uuid import UUID

from ..meta import Type, EntityState, MountConfig, SubnetConfig
from ..serializable import Serializable


class Entity(Serializable, ABC):
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

    @abstractmethod
    def get_type(self) -> Type:
        pass

    @abstractmethod
    def inf_name(self) -> str:
        pass

    @abstractmethod
    def get_id(self) -> UUID:
        pass

    @abstractmethod
    def real_name(self) -> str:
        pass

    @abstractmethod
    def state(self) -> EntityState:
        pass
