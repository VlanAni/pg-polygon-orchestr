# abstract class for nodes (docker, claude, PXE, qemu and others...)

from abc import ABC, abstractmethod

from .exec_result import ExecResult
from ..configs.node_config import NodeConfig


class Node(ABC):

    @abstractmethod
    def start(self) -> None:
        # run a new container from image or start a container
        pass

    @abstractmethod
    def stop(self, timeout: int) -> None:
        # stop container
        pass

    @abstractmethod
    def exec(self, command: str) -> ExecResult | None:
        pass

    @abstractmethod
    def update_configuration(self, new_config: NodeConfig) -> None:
        pass

    @abstractmethod
    def get_node_network_ip(self, net_name: str) -> str | None:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass
