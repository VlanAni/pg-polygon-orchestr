from ..common_types import Mountable, MountableType


class HostPathDesc(Mountable):
    """Класс, описывающий директорию/файл на хосте

    `path` - путь на хосте

    """

    def __init__(self, path: str):
        self.__path = path

    @property
    def source(self) -> str:
        return self.__path

    @property
    def mtype(self) -> MountableType:
        return MountableType.HOSTPATH
