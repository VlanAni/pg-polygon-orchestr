from .infrastructure import Infrastructure
from .docker_node import DockerNode

from docker.models import networks as docker_networks


class DockerInfrastructure(Infrastructure):

    def __init__(
        self,
        nodes: dict[str, DockerNode],
        networks: dict[str, docker_networks.Network] | None = None,
    ) -> None:
        self.__nodes = nodes.copy()
        self.__alive = True
        self.__networks = networks.copy() if networks else {}

    # геттеры
    def get_network_ip_addr(self, net_name: str) -> str | None:

        net_obj = self.__networks.get(net_name, None)

        if net_obj is None:
            return None

        net_obj.reload()

        if net_obj.attrs["IPAM"]["Config"] is None or []:
            return None

        return net_obj.attrs["IPAM"]["Config"][0]["Subnet"]

    def get_node_ip_in_network(self, node_name: str, net_name: str) -> str | None:

        node = self.__nodes.get(node_name, None)

        if node is None:
            return None

        return node.get_node_network_ip(net_name=net_name)

    def is_alive(self) -> bool:
        return self.__alive

    def get_nodes(self) -> dict[str, DockerNode]:
        return self.__nodes.copy()

    def get_node_object(self, node_name: str) -> DockerNode | None:
        return self.__nodes.get(node_name, None)

    # сеттеры
    def mark_as_not_alive(self) -> None:
        self.__alive = False
