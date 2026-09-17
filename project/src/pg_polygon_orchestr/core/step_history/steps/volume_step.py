from types import MappingProxyType
from typing import Any, Mapping

from ..infra_object_type import InfraObjectType

from .step import Step
from ..actions.volume_action import VolumeAction
from ..actions.action import Action


class VolumeStep(Step):

    def __init__(self, volume_name: str, action: VolumeAction):

        self.__volume_name = volume_name
        self.__action = action
        self.__args: dict[str, Any] = {}

    @property
    def action(self) -> Action:
        return self.__action

    @property
    def obj_type(self) -> InfraObjectType:
        return InfraObjectType.VOLUME

    @property
    def args(self) -> MappingProxyType[str, Any]:
        return MappingProxyType(self.__args)

    def serialize(self) -> Mapping[str, Any]:
        return {
            "type": self.obj_type,
            "action": self.action,
            "volume_name": self.__volume_name,
            "args": self.args,
        }
