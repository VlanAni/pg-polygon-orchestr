import ipaddress
from types import MappingProxyType
from typing import Any, Mapping

from ..infra_object_type import InfraObjectType

from .step import Step
from ..actions.net_action import NetAction
from ..actions.action import Action

from ...common_types import SubnetConfig


class NetStep(Step):

    def __init__(
        self,
        network_name: str,
        action: NetAction,
        node_name: str = "",
        subnet_configs: list[SubnetConfig] | None = None,
        subnet_label: str = "",
        addr: ipaddress.IPv4Address | None = None,
    ):
        self.__network_name = network_name
        self.__action: NetAction = action

        match action:

            case NetAction.REMOVE:

                self.__args: dict[str, Any] = {}

            case NetAction.DEPLOY:

                if subnet_configs is None:
                    raise KeyError(
                        "subnet_configs must be specified to deploy the network"
                    )

                self.__args = {
                    "subnet_configs": subnet_configs,
                }

            case NetAction.DISCONNET if node_name is "":

                self.__args = {
                    "node": node_name,
                }

            case NetAction.CONNECT if node_name is "":

                if not (subnet_label):
                    self.__args = {
                        "node": node_name,
                        "subnet_label": subnet_label,
                        "addr": addr,
                    }

            case _:

                raise KeyError(
                    f"node must be specified for connect/disconnect operations"
                )

    @property
    def action(self) -> Action:
        return self.__action

    @property
    def obj_type(self) -> InfraObjectType:
        return InfraObjectType.NETWORK

    @property
    def args(self) -> MappingProxyType[str, Any]:
        return MappingProxyType(self.__args)

    def serialize(self) -> Mapping[str, Any]:
        return {
            "type": self.obj_type,
            "action": self.action,
            "network_name": self.__network_name,
            "args": self.args,
        }
