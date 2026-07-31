from .node import Node
from .exec_result import ExecResult
from ..configs.node_config import NodeConfig
from ..exception.common_exceptions import (
    NodeIsNotDeployer,
    FailedToStartNode,
    FailedToStopNode,
    FailedToExecuteCommand,
    FailedToUpdateConfiguration,
    FailedToGetIP,
)


class NodeLink(Node):

    def __init__(self, name: str, config: NodeConfig):
        self.__node: Node | None = None
        self.__name: str = name
        self.__config: NodeConfig = config

    # ----- ИНТЕРФЕЙСНЫЕ МЕТОДЫ

    def start(self) -> None:
        if self.__node:
            try:
                self.__node.start()
                return
            except Exception as err:
                raise FailedToStartNode(f"failed to start node {self.__name}") from err

        raise NodeIsNotDeployer(f"node {self.__name} is not deployer")

    def stop(self, timeout: int) -> None:
        if self.__node:
            try:
                self.__node.stop(timeout=timeout)
                return
            except Exception as err:
                raise FailedToStopNode(f"failed to stop node {self.__name}") from err

        raise NodeIsNotDeployer(f"node {self.__name} is not deployer")

    def exec(self, command: str) -> ExecResult | None:
        if self.__node:
            try:
                return self.__node.exec(command=command)
            except Exception as err:
                raise FailedToExecuteCommand(
                    f"failed to execute a command {command} on the node {self.__name}"
                ) from err

        raise NodeIsNotDeployer(f"node {self.__name} is not deployer")

    def update_configuration(self, new_config: NodeConfig) -> None:
        if self.__node:
            try:
                self.__node.update_configuration(new_config=new_config)
                return
            except Exception as err:
                raise FailedToUpdateConfiguration(
                    f"failed to update configuration on node {self.__name}"
                ) from err

        raise NodeIsNotDeployer(f"node {self.__name} is not deployer")

    def get_node_network_ip(self, net_name: str) -> str | None:
        if self.__node:
            try:
                return self.__node.get_node_network_ip(net_name=net_name)
            except Exception as err:
                raise FailedToGetIP(
                    f"failed to get {self.__name}' ip in the network {net_name}"
                ) from err

        raise NodeIsNotDeployer(f"node {self.__name} is not deployer")

    # ----- УПРАВЛЕНИЕ ПОДКАПОТНОЙ НОДОЙ

    def set_deployed(self, node: Node) -> None:
        self.__node = node

    def set_undeployer(self) -> None:
        self.__node = None

    # ----- ГЕТТЕРЫ

    def get_configuration(self) -> NodeConfig:
        return self.__config

    def get_name(self) -> str:
        return self.__name
