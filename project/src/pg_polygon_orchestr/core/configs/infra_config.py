from .node_config import NodeConfig
from .net_config import NetConfig
from ..exception.common_exceptions import NetConfigIncludeNotConfiguredNodeException

import copy


class InfConfig:

    def __init__(self, node_configs: dict[str, NodeConfig] | None = None) -> None:
        self.__node_configs = (
            copy.deepcopy(node_configs) if node_configs is not None else {}
        )

        self.__net_configs: dict[str, NetConfig] = dict()
        self.__net_registry: dict[str, list[str]] = dict()

    def put_node_config(self, node_name: str, config: NodeConfig) -> bool:
        if self.__node_configs.get(node_name, None) is None:
            self.__node_configs[node_name] = config
            self.__net_registry[node_name] = []
            return True

        return False

    def put_net_config(self, net_name: str, config: NetConfig) -> bool:
        if self.__net_configs.get(net_name, None) is not None:
            return False

        for node_name in config.get_nodes():
            if self.__node_configs.get(node_name, None) is None:
                self.__delete_net_from_net_registry(net_name=net_name)

                raise NetConfigIncludeNotConfiguredNodeException(
                    f"network {net_name} has the not configured node {node_name}"
                )
            else:
                self.__registr_node_into_network(node_name=node_name, net_name=net_name)

        self.__net_configs[net_name] = config

        return True

    def get_node_names(self) -> list[str]:
        return list(self.__node_configs.keys())

    def get_node_config(self, name: str) -> NodeConfig | None:
        return self.__node_configs.get(name, None)

    def get_net_names(self) -> list[str]:
        return list(self.__net_configs.keys())

    def get_net_config(self, name: str) -> NetConfig | None:
        return self.__net_configs.get(name, None)

    def get_node_net_data(self, node_name: str) -> list[str] | None:
        connected_networks = self.__net_registry.get(node_name, None)

        return connected_networks.copy() if connected_networks is not None else None

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
