class NetConfig:
    def __init__(
        self,
        name: str,
        ipv6: bool,
        internal: bool,
        nodes: list[str],
        driver: str = "bridge",
    ):
        self.__name = name
        self.__ipv6 = ipv6
        self.__internal = internal
        self.__nodes = nodes.copy()
        self.__driver = driver

    def get_nodes(self) -> list[str]:
        return self.__nodes.copy()

    def name(self) -> str:
        return self.__name

    def is_internal(self) -> bool:
        return self.__internal

    def ipv6_support(self) -> bool:
        return self.__ipv6

    def driver(self) -> str:
        return self.__driver
