from abc import abstractmethod

from .entity import Entity
from .node import Node


class Network(Entity):

    @abstractmethod
    def get_network_ip(self) -> str:
        pass

    @abstractmethod
    def connect_node(
        self, node: Node, ipv4_addr: str | None = None, ipv6_addr: str | None = None
    ) -> None:
        pass

    @abstractmethod
    def disconnect_node(self, node: Node) -> None:
        pass

    @abstractmethod
    def get_node_network_ip(self, node: Node, ipv6: bool = False) -> str:
        pass
