from types import MappingProxyType
from typing import Any, Mapping

from ..infra_object_type import InfraObjectType

from .step import Step
from ..actions.node_action import NodeAction
from ...common_types import BindMountConfig
from ...configs import NodeConfig
from ..actions.action import Action


class NodeStep(Step):

    def __init__(
        self,
        node_name: str,
        action: NodeAction,
        mount_configs: list[BindMountConfig] = [],
        command: str = "",
        timeout: int | None = None,
        new_config: NodeConfig | None = None,
    ):
        self.__node_name = node_name
        self.__action = action

        match action:

            case NodeAction.DEPLOY:

                self.__args: dict[str, Any] = {
                    "mount_configs": mount_configs,
                }

            case NodeAction.UPDATE:

                if not (new_config):
                    raise KeyError("new_config must be specified to update")

                self.__args = {
                    "new_config": new_config,
                }

            case NodeAction.EXEC:

                if not command:
                    raise KeyError("command must be specified to execute")

                self.__args = {
                    "command": command,
                }

            case NodeAction.STOP:

                if not timeout:
                    raise KeyError("timeout must be specified to stop")

                self.__args = {
                    "timeout": timeout,
                }

            case _:
                pass

    @property
    def action(self) -> Action:
        return self.__action

    @property
    def obj_type(self) -> InfraObjectType:
        return InfraObjectType.NODE

    @property
    def args(self) -> MappingProxyType[str, Any]:
        return MappingProxyType(self.__args)

    def serialize(self) -> Mapping[str, Any]:
        return {
            "type": self.obj_type,
            "action": self.action,
            "node_name": self.__node_name,
            "args": self.args,
        }
