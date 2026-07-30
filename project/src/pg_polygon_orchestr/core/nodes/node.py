# abstract class for nodes (docker, claude, PXE, qemu and others...)

from abc import ABC, abstractmethod

from .exec_result import ExecResult


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
    def exec(self, command: str) -> ExecResult:
        pass
