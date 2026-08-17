from abc import ABC, abstractmethod
from uuid import UUID
import typing

from ..meta import Type, EntityState, MountConfig


class Entity(ABC):

    @abstractmethod
    def deploy(self, **options: str | list[MountConfig]):
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
    def transform_to_mapping(self) -> typing.Mapping[str, typing.Any]:
        pass

    @abstractmethod
    def state(self) -> EntityState:
        pass
