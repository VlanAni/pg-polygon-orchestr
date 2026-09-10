from json import JSONEncoder
import typing
from uuid import UUID
import enum
import ipaddress

from ..serializable import Serializable


class CustomEncoder(JSONEncoder):
    def default(self, o: typing.Any) -> typing.Any:
        if isinstance(o, Serializable):
            return o.serialize()

        if isinstance(o, UUID):
            return str(o)

        if isinstance(o, enum.Enum):
            return o.name

        if isinstance(o, ipaddress.IPv4Address | ipaddress.IPv6Address):
            return str(o)

        if isinstance(o, ipaddress.IPv4Network | ipaddress.IPv6Network):
            return o.with_prefixlen

        return super().default(o=o)
