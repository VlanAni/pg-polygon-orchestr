# abstract class for deploying nodes using its config

from abc import ABC, abstractmethod

from ..nodes.node import Node

from ..configs.node_config import NodeConfig

from ..configs.infra_config import InfConfig

from ..nodes.infrastructure import Infrastructure


class Deployer(ABC):

    @abstractmethod
    def deploy_node(self, config: NodeConfig) -> Node:
        pass

    @abstractmethod
    def destroy_everything(self) -> None:
        pass

    @abstractmethod
    def deploy_infrastructure(self, inf_config: InfConfig) -> Infrastructure:
        pass
