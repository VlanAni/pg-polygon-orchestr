from abc import abstractmethod
import typing

from .infra_object import InfraObject

from ..common_types import InfraType, EntityState
from ..serializable import Serializable


class Entity(Serializable, InfraObject):

    @abstractmethod
    def deploy(self, **options: typing.Any):
        pass

    @abstractmethod
    def undeploy(self):
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
