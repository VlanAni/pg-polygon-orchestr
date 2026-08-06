# abstract class for nodes (docker, claude, PXE, qemu and others...)

from abc import abstractmethod

from .exec_result import ExecResult
from ..configs.node_config import NodeConfig
from .entity import Entity
from .mount_config import MountConfig


class Node(Entity):

    @abstractmethod
    def start(self, mount_configs: list[MountConfig] = []) -> None:
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
