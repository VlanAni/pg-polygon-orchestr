# abstract class for nodes (docker, claude, PXE, qemu and others...)

from abc import abstractmethod

from ..infra_configs import NodeConfig
from ..common_interfaces import Entity
from ..common_types import ExecResult


class Node(Entity):

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self, timeout: int) -> None:
        pass

    @abstractmethod
    def exec(self, command: str) -> ExecResult | None:
        pass

    @abstractmethod
    def update(self, new_config: NodeConfig) -> None:
        pass
