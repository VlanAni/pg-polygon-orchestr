from json import JSONEncoder
import typing
import types
from uuid import UUID
import enum
import ipaddress

from ..serializable import Serializable


class PgPolygonEncoder(JSONEncoder):
    def default(self, o: typing.Any) -> typing.Any:
        if isinstance(o, Serializable):
            return o.serialize()

        if isinstance(o, UUID):
            return str(o)

        if isinstance(o, types.MappingProxyType):
            return dict(o)  # type: ignore

        if isinstance(o, enum.Enum):
            return o.name

        if isinstance(o, ipaddress.IPv4Address | ipaddress.IPv6Address):
            return str(o)

        if isinstance(o, ipaddress.IPv4Network | ipaddress.IPv6Network):
            return o.with_prefixlen

        return super().default(o=o)
