# abstract class for deploying nodes using its config

from abc import ABC, abstractmethod

from ..nodes.node import Node

from ..configs.node_config import NodeConfig


class Deployer(ABC):

    @abstractmethod
    def deploy(self, config: NodeConfig) -> Node:
        pass

    @abstractmethod
    def destroy_everything(self) -> None:
        pass
