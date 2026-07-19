# abstract class for deploying nodes using its config

from abc import ABC, abstractmethod

from ..nodes.node import Node

from ..configs.config import Config


class Deployer(ABC):

    @abstractmethod
    def deploy(self, config: Config) -> Node:
        pass

    @abstractmethod
    def destroy_everything(self) -> None:
        pass
