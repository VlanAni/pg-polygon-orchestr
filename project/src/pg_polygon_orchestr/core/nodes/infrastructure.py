from abc import ABC, abstractmethod

from .exec_result import ExecResult
from ..configs.node_config import NodeConfig


class Infrastructure(ABC):

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self, timeout: int) -> None:
        pass

    @abstractmethod
    def exec_command_on_node(self, node_name: str, command: str) -> ExecResult | None:
        pass

    def update_configuration(self, new_config: NodeConfig, node_name: str) -> None:
        pass
