from .node import Node
from .exec_result import ExecResult
from ..configs.node_config import NodeConfig


class NodeLink(Node):

    def __init__(self):
        self.__read_node: Node | None = None

    # ----- ИНТЕРФЕЙСНЫЕ МЕТОДЫ

    def start(self) -> None:
        if self.__read_node:
            self.__read_node.start()

    def stop(self, timeout: int) -> None:
        if self.__read_node:
            self.__read_node.stop(timeout=timeout)

    def exec(self, command: str) -> ExecResult | None:
        if self.__read_node:
            return self.__read_node.exec(command=command)

        return None

    def update_configuration(self, new_config: NodeConfig) -> None:
        if self.__read_node:
            self.__read_node.update_configuration(new_config=new_config)

    # ----- КОНФИГУРАЦИЯ ПОДКАПОТНОЙ НОДЫ

    def set_real_node(self, value: Node | None) -> None:
        self.__read_node = value
