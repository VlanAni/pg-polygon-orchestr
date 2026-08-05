# abstract class for deploying nodes using its config

from abc import ABC, abstractmethod


from .node import Node
from .volume import Volume
from .network import Network

from ..configs import net_config, node_config, volume_config


class Deployer(ABC):

    # ----- ДЕПЛОИНГ ИНФРАСТРУКТУРЫ

    @abstractmethod
    def deploy_infrastructure(self) -> None:
        pass

    @abstractmethod
    def clean_infrastructure(self) -> None:
        pass

    @abstractmethod
    def remove_infrastructure(self) -> None:
        pass

    # ----- КОНФИГУРАЦИЯ

    @abstractmethod
    def put_node_config(self, config: node_config.NodeConfig) -> Node:
        pass

    @abstractmethod
    def put_volume_config(self, config: volume_config.VolumeConfig) -> Volume:
        pass

    @abstractmethod
    def put_network_config(self, config: net_config.NetConfig) -> Network:
        pass

    # ----- ГЕТТЕРЫ

    @abstractmethod
    def get_nodes(self) -> dict[str, Node]:
        pass

    @abstractmethod
    def get_volumes(self) -> dict[str, Volume]:
        pass

    @abstractmethod
    def get_network(self) -> dict[str, Network]:
        pass
