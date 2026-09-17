from abc import abstractmethod
import ipaddress

from .entity import Entity
from .node import Node
from ..meta import ConnectionInfo, SubnetInfo


class Network(Entity):

    @abstractmethod
    def subnets(self) -> list[SubnetInfo]:
        pass

    @abstractmethod
    def connect(
        self,
        node: Node | str,
        subnet_label: str,
        addr: ipaddress.IPv4Address | None = None,
    ) -> None:
        pass

    @abstractmethod
    def disconnect(self, node: Node | str) -> None:
        pass

    @abstractmethod
    def get_node_connection_info(self, node: Node) -> ConnectionInfo:
        pass
