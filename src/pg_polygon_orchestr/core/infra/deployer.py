# abstract class for deploying nodes using its config

from abc import abstractmethod
from typing import Mapping

from .node import Node
from .network import Network
from ..common_interfaces import InfraObject
from ..infra_configs import NetConfig, NodeConfig
from ..common_types import SnapshotDescription
from ..serializable import Serializable


class Deployer(Serializable, InfraObject):
    """Интерфейс `Deployer`

    Предоставляет методы для управления инфраструктурой

    """

    @abstractmethod
    def destroy_infra(self) -> None:
        """Выполнить `remove()` для всех элементов инфраструктуры
        Raises:
            common_exception.RemoveError: не получилось выполнить `deploy()` для всех элементов
        """
        pass

    # ----- КОНФИГУРАЦИЯ

    @abstractmethod
    def node_from_config(self, name: str, config: NodeConfig) -> Node:
        """Зарегистрировать конфиг узла `config` на имя узла `name`

        Args:
            `name` (`str`): имя для узла в инфраструктуре (будет соответствовать возвращаемому значению `node.inf_name()`)
            `config` (`NodeConfig`): конфигурация этого узла

        Returns:
            `Node`: если узел с таким именем уже был сконфигурирован - вернётся ранее сконфигурированый узел, иначе - новый сконфигурированный узел
        """
        pass

    @abstractmethod
    def network_from_config(self, name: str, config: NetConfig) -> Network:
        """Зарегистрировать конфиг `config` на имя сети `name`

        Args:
            `name` (`str`): имя для сети в инфраструктуре (будет соответствовать возвращаемому значению `network.inf_name()`)
            `config` (`NetConfig`): конфигурация этой сети

        Returns:
            `Network`: если `Network` с таким именем уже был сконфигурирован - вернётся ранее сконфигурированый `Network`, иначе - новый сконфигурированный `Network` с конфигом `config`
        """
        pass

    # ----- ГЕТТЕРЫ

    @property
    @abstractmethod
    def nodes(self) -> Mapping[str, Node]:
        """Вернуть все узлы инфраструктуры

        Returns:
            Mapping[str, Node]: `read_only` копия словаря, где ключ - `uuid` узла, а значение - `Node`
        """
        pass

    @property
    @abstractmethod
    def network(self) -> Mapping[str, Network]:
        """Вернуть все сети инфраструктуры

        Returns:
            Mapping[str, Network]: `read_only` копия словаря, где ключ - `uuid` сети, а значение - `Network` сети
        """
        pass

    # ----- SNAPSHOTS

    @abstractmethod
    def make_snapshot(
        self, snapshot_name: str = "", online: bool = False
    ) -> SnapshotDescription:
        pass
