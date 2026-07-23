from .node_config import NodeConfig


class InfConfig:

    def __init__(self, configs: list[NodeConfig] = []) -> None:
        self.__configs = configs.copy()

    def add_config(self, config: NodeConfig) -> None:
        self.__configs.append(config)

    def get_configs(self) -> list[NodeConfig]:
        return self.__configs.copy()
