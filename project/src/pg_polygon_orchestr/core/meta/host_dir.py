from .mounted import Mountable, MountableType


class HostPathDesc(Mountable):

    def __init__(self, path: str):
        self.__path = path

    def source(self) -> str:
        return self.__path

    def mtype(self) -> MountableType:
        return MountableType.HOSTPATH
