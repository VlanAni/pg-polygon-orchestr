# abstract class for deploying nodes using its config

from abc import ABC, abstractmethod
from typing import Any, Mapping
import uuid

from .node import Node
from .volume import Volume
from .network import Network

from ..configs import NetConfig, NodeConfig, VolumeConfig
from ..meta import SnapshotDescription


class Deployer(ABC):
    """Интерфейс `Deployer`

    Предоставляет методы для управления инфраструктурой

    """

    # ----- ДЕПЛОИНГ ИНФРАСТРУКТУРЫ

    @abstractmethod
    def deploy_infrastructure(self) -> None:
        """Выполнить `deploy()` для всех элементов инфраструктуры без дополнительных опций
        Raises:
            common_exception.DeployError: не получилось выполнить `deploy()` для всех элементов
        """
        pass

    @abstractmethod
    def clear_infrastructure(self) -> None:
        """Выполнить `clear()` для всех элементов инфраструктуры
        Raises:
            common_exception.ClearError: не получилось выполнить `deploy()` для всех элементов
        """
        pass

    @abstractmethod
    def remove_infrastructure(self) -> None:
        """Выполнить `remove()` для всех элементов инфраструктуры
        Raises:
            common_exception.RemoveError: не получилось выполнить `deploy()` для всех элементов
        """
        pass

    # ----- КОНФИГУРАЦИЯ

    @abstractmethod
    def put_node_config(self, name: str, config: NodeConfig) -> Node:
        """Зарегистрировать конфиг узла `config` на имя узла `name`

        Args:
            `name` (`str`): имя для узла в инфраструктуре (будет соответствовать возвращаемому значению `node.inf_name()`)
            `config` (`NodeConfig`): конфигурация этого узла

        Returns:
            `Node`: если узел с таким именем уже был сконфигурирован - вернётся ранее сконфигурированый узел, иначе - новый сконфигурированный узел
        """
        pass

    @abstractmethod
    def put_volume_config(self, name: str, config: VolumeConfig) -> Volume:
        """Зарегистрировать конфиг `config` на имя Volume'а `name`

        Args:
            `name` (`str`): имя для Volume в инфраструктуре (будет соответствовать возвращаемому значению `volume.inf_name()`)
            `config` (`VolumeConfig`): конфигурация этого Volume

        Returns:
            `Volume`: если `Volume` с таким именем уже был сконфигурирован - вернётся ранее сконфигурированый `Volume`, иначе - новый сконфигурированный `Volume` с конфигом `config`
        """
        pass

    @abstractmethod
    def put_network_config(self, name: str, config: NetConfig) -> Network:
        """Зарегистрировать конфиг `config` на имя сети `name`

        Args:
            `name` (`str`): имя для сети в инфраструктуре (будет соответствовать возвращаемому значению `network.inf_name()`)
            `config` (`NetConfig`): конфигурация этой сети

        Returns:
            `Network`: если `Network` с таким именем уже был сконфигурирован - вернётся ранее сконфигурированый `Network`, иначе - новый сконфигурированный `Network` с конфигом `config`
        """
        pass

    # ----- ГЕТТЕРЫ

    @abstractmethod
    def get_nodes(self) -> Mapping[str, Node]:
        """Вернуть все узлы инфраструктуры

        Returns:
            Mapping[str, Node]: `read_only` копия словаря, где ключ - `uuid` узла, а значение - `Node`
        """
        pass

    @abstractmethod
    def get_volumes(self) -> Mapping[str, Volume]:
        """Вернуть все Volume инфраструктуры

        Returns:
            Mapping[str, Volume]: `read_only` копия словаря, где ключ - `uuid` Volume, а значение - `Volume`
        """
        pass

    @abstractmethod
    def get_network(self) -> Mapping[str, Network]:
        """Вернуть все сети инфраструктуры

        Returns:
            Mapping[str, Network]: `read_only` копия словаря, где ключ - `uuid` сети, а значение - `Network` сети
        """
        pass

    @abstractmethod
    def get_id(self) -> uuid.UUID:
        """Уникальнй идентификатор инфраструктуры из 128 бит

        Returns:
            uuid.UUID: `uuid` инфраструктуры
        """
        pass

    # ----- SNAPSHOTS

    @abstractmethod
    def transform_to_mapping(self) -> Mapping[str, Any]:
        pass

    @abstractmethod
    def make_snapshot(
        self, snapshot_name: str = "", online: bool = False
    ) -> SnapshotDescription:
        pass
