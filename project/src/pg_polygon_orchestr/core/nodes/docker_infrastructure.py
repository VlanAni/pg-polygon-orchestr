from .infrastructure import Infrastructure
from .docker_node import DockerNode
from ..configs.node_config import NodeConfig


class DockerInfrastructure(Infrastructure):

    def __init__(self, nodes: list[DockerNode]) -> None:
        self.__nodes = self.__init_nodes_dict(nodes)
        self.__usable = True

    def __init_nodes_dict(self, nodes: list[DockerNode]) -> dict[str, DockerNode]:
        nodes_dict: dict[str, DockerNode] = dict()

        for node in nodes:
            nodes_dict[f"node_{node.get_id()}"] = node

        return nodes_dict

    def start(self) -> bool:
        started = 0

        if not (self.__usable):
            return False

        nodes = list(self.__nodes.values())

        for node in nodes:
            res = node.start()

            if not (res):

                for i in range(0, started):
                    nodes[i].stop(0)

                return False
            else:
                started += 1

        return True

    def stop(self, timeout: int) -> bool:
        if not (self.__usable):
            return False

        for node in self.__nodes.values():
            res = node.stop(timeout=timeout)

            if not (res):
                return False

        return True

    def mask_as_unusable(self) -> None:
        self.__usable = False

    def get_usable(self) -> bool:
        return self.__usable

    def get_nodes(self) -> dict[str, DockerNode]:
        return self.__nodes.copy()

    def update_configuration(self, new_config: NodeConfig, node_name: str) -> bool:
        if not (self.__usable):
            return False

        node = self.__nodes.get(node_name, None)

        if node is None:
            return False
        else:
            return node.update_configuration(new_config=new_config)
