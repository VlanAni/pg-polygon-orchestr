from .node_config import NodeConfig

import copy


class InfConfig:

    def __init__(self, configs: dict[str, NodeConfig] | None = None) -> None:
        self.__configs = copy.deepcopy(configs) if configs is not None else {}

    def put_config(self, node_name: str, config: NodeConfig) -> bool:
        if self.__configs.get(node_name, None) is None:
            self.__configs[node_name] = config
            return True

        return False

    def get_names(self) -> list[str]:
        return list(self.__configs.keys())

    def get_config(self, name: str):
        return self.__configs.get(name, None)
