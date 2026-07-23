from .infrastructure import Infrastructure
from .docker_node import DockerNode


class DockerInfrastructure(Infrastructure):

    def __init__(self, nodes: list[DockerNode]) -> None:
        self.__nodes = nodes.copy()
        self.__usable = True

    def run(self) -> bool:
        if not (self.__usable):
            return False

        for node in self.__nodes:
            res = node.start()

            if not (res):
                return False

        return True

    def freeze(self, timeout: int) -> bool:
        if not (self.__usable):
            return False

        for node in self.__nodes:
            res = node.stop(timeout=timeout)

            if not (res):
                return False

        return True

    def mask_as_unusable(self) -> None:
        self.__usable = False
