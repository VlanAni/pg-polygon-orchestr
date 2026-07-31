from .node_config import NodeConfig
from .net_config import NetConfig
from .docker_volume_config import VolumeConfig
from ..exception import common_exceptions
from ..nodes.node_link import NodeLink
from ..nodes.node import Node


class InfConfig:

    def __init__(self) -> None:
        self.__net_configs: dict[str, NetConfig] = dict()
        self.__net_registry: dict[str, list[str]] = dict()
        self.__docker_volume_configs: dict[str, VolumeConfig] = dict()
        self.__node_links: dict[str, NodeLink] = dict()

    # ----- УПАКОВКА КОНФИГОВ

    def put_node_config(self, config: NodeConfig) -> Node | None:
        node_name = config.name

        if self.__node_links.get(node_name, None) is None:
            node = NodeLink(name=node_name, config=config)
            self.__node_links[node_name] = node
            self.__net_registry[node_name] = []
            return node

        return None

    def put_net_config(self, config: NetConfig) -> bool:
        net_name = config.name()

        if self.__net_configs.get(net_name, None) is not None:
            return False

        for node_name in config.get_nodes():
            if self.__node_links.get(node_name, None) is None:
                self.__delete_net_from_net_registry(net_name=net_name)

                raise common_exceptions.NetConfigIncludeNotConfiguredNodeException(
                    f"network {net_name} has the not configured node {node_name}"
                )
            else:
                self.__registr_node_into_network(node_name=node_name, net_name=net_name)

        self.__net_configs[net_name] = config

        return True

    def put_volume_config(self, config: VolumeConfig) -> bool:
        if self.__docker_volume_configs.get(config.name(), None) is not None:
            return False

        volume_name = config.name()
        node_name = config.owner_name()

        if self.__node_links.get(node_name, None) is None:
            raise common_exceptions.DockerVolumeConfigIncludeNotConfiguredNode(
                f"the volume {volume_name} include {node_name} which is not configured"
            )

        self.__docker_volume_configs[volume_name] = config

        return True

    # ----- ГЕТТЕРЫ

    def get_node_names(self) -> list[str]:
        return list(self.__node_links.keys())

    def get_node_link(self, name: str) -> NodeLink | None:
        return self.__node_links.get(name, None)

    def get_net_names(self) -> list[str]:
        return list(self.__net_configs.keys())

    def get_net_config(self, name: str) -> NetConfig | None:
        return self.__net_configs.get(name, None)

    def get_node_net_data(self, node_name: str) -> list[str] | None:
        connected_networks = self.__net_registry.get(node_name, None)

        return connected_networks.copy() if connected_networks is not None else None

    def get_volumes(self) -> list[VolumeConfig]:
        return list(self.__docker_volume_configs.values())

    # ----- ПРИВАТНЫЕ МЕТОДЫ

    def __registr_node_into_network(self, node_name: str, net_name: str) -> None:
        if self.__net_registry.get(node_name, None) is None:
            self.__net_registry[node_name] = [net_name]
        else:
            self.__net_registry[node_name].append(net_name)

    def __delete_net_from_net_registry(self, net_name: str) -> None:
        for net_list in self.__net_registry.values():
            try:
                net_list.remove(net_name)
            except ValueError:
                pass
