from abc import abstractmethod
import types
import typing

from ..actions.action import Action
from ...serializable import Serializable
from ..infra_object_type import InfraObjectType


class Step(Serializable):

    @property
    @abstractmethod
    def action(self) -> Action:
        pass

    @property
    @abstractmethod
    def obj_type(self) -> InfraObjectType:
        pass

    @property
    @abstractmethod
    def args(self) -> types.MappingProxyType[str, typing.Any]:
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: typing.Mapping[str, typing.Any]) -> Step: ...
