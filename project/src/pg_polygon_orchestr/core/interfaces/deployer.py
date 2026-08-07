# abstract class for deploying nodes using its config

from abc import ABC, abstractmethod
from collections.abc import Mapping

from .node import Node
from .volume import Volume
from .network import Network

from ..configs import NetConfig, NodeConfig, VolumeConfig


class Deployer(ABC):

    # ----- ДЕПЛОИНГ ИНФРАСТРУКТУРЫ

    @abstractmethod
    def deploy_infrastructure(self) -> None:
        pass

    @abstractmethod
    def clear_infrastructure(self) -> None:
        pass

    @abstractmethod
    def remove_infrastructure(self) -> None:
        pass

    # ----- КОНФИГУРАЦИЯ

    @abstractmethod
    def put_node_config(self, name: str, config: NodeConfig) -> Node:
        pass

    @abstractmethod
    def put_volume_config(self, name: str, config: VolumeConfig) -> Volume:
        pass

    @abstractmethod
    def put_network_config(self, name: str, config: NetConfig) -> Network:
        pass

    # ----- ГЕТТЕРЫ

    @abstractmethod
    def get_nodes(self) -> Mapping[str, Node]:
        pass

    @abstractmethod
    def get_volumes(self) -> Mapping[str, Volume]:
        pass

    @abstractmethod
    def get_network(self) -> Mapping[str, Network]:
        pass
