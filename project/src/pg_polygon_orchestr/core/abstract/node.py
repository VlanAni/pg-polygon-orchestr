# abstract class for nodes (docker, claude, PXE, qemu and others...)

from abc import abstractmethod

from ..configs import NodeConfig
from .entity import Entity
from ..meta import ExecResult


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
