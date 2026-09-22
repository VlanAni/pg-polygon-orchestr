from types import MappingProxyType
import typing

from ..actions.action import Action
from ..infra_object_type import InfraObjectType

from .step import Step
from ..actions.deployer_action import DeployerAction

from ...configs import Config
from ...configs import NetConfig, NodeConfig, VolumeConfig


class DeployerStep(Step):

    def __init__(
        self,
        action: DeployerAction,
        snapshot_name: str = "",
        online: bool = False,
        name: str = "",
        config: Config | None = None,
    ):
        self.__action: DeployerAction = action
        match action:

            case DeployerAction.MAKE_SNAPSHOT:

                self.__args: dict[str, typing.Any] = {
                    "snapshot_name": snapshot_name,
                    "online": online,
                }
                return

            case DeployerAction.REMOVE_INFRASTRUCTURE:
                self.__args = {}
                return

            case DeployerAction.PUT_NET_CONFIG if (not name) or (not config):

                if not isinstance(config, NetConfig):
                    raise KeyError(f"config must be of the type {type(NetConfig)}")

            case DeployerAction.PUT_NODE_CONFIG if (not name) or (not config):

                if not isinstance(config, NodeConfig):
                    raise KeyError(f"config must be of the type {type(NodeConfig)}")

            case DeployerAction.PUT_VOLUME_CONFIG if (not name) or (not config):

                if not isinstance(config, VolumeConfig):
                    raise KeyError(f"config must be of the type {type(VolumeConfig)}")

            case _:

                raise KeyError(
                    f"name and config params must be non-null for put_*_config function"
                )

        self.__args = {
            "name": name,
            "config": config,
        }

    @property
    def action(self) -> Action:
        return self.__action

    @property
    def obj_type(self) -> InfraObjectType:
        return InfraObjectType.DEPLOYER

    @property
    def args(self) -> MappingProxyType[str, typing.Any]:
        return MappingProxyType(self.__args)

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        return {
            "type": self.obj_type,
            "action": self.action,
            "args": self.args,
        }

    @classmethod
    def from_dict(cls, data: typing.Mapping[str, typing.Any]) -> Step:
        try:
            if data["type"] != InfraObjectType.DEPLOYER.name:
                raise KeyError(f"step type must be DEPLOYER")
        except Exception as err:
            raise KeyError(f"failed to get the type") from err

        try: 
            action = InfraObjectType() data['action']
