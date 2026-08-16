from pg_polygon_orchestr.core.meta.mounted import MountableType

from .entity import Entity
from ..meta import Mountable, MountableType


class Volume(Entity, Mountable):

    def mtype(self) -> MountableType:
        return MountableType.VOLUME
