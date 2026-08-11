from abc import ABC, abstractmethod
from uuid import UUID
import typing

from ..meta import Type


class Entity(ABC):

    @abstractmethod
    def deploy(self):
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
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_id(self) -> UUID:
        pass

    @abstractmethod
    def transform_to_mapping(self) -> typing.Mapping[str, typing.Any]:
        pass
