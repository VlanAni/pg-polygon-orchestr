# abstract class for nodes (docker, claude, PXE, qemu and others...)

from abc import ABC, abstractmethod


class Node(ABC):

    @abstractmethod
    def start(self) -> bool:
        # run a new container from image or start a container
        pass

    @abstractmethod
    def stop(self, timeout: int) -> bool:
        # stop container
        pass
