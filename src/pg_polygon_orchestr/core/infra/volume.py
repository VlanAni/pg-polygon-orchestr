from pg_polygon_orchestr.core.common_types.mounted import MountableType

from ..common_interfaces import Entity
from ..common_types import Mountable, MountableType


class Volume(Entity, Mountable):

    @property
    def mtype(self) -> MountableType:
        return MountableType.VOLUME
