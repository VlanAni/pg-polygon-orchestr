from .mounted import Mountable, MountableType


class HostPathDesc(Mountable):
    """Класс, описывающий директорию/файл на хосте

    `path` - путь на хосте

    """

    def __init__(self, path: str):
        self.__path = path

    def source(self) -> str:
        return self.__path

    def mtype(self) -> MountableType:
        return MountableType.HOSTPATH
