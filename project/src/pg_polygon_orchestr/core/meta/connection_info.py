from dataclasses import dataclass, fields
import ipaddress
from typing import Any, Mapping

from ..serializable import Serializable


@dataclass(frozen=True)
class ConnectionInfo(Serializable):
    subnet_label: str
    addr: ipaddress.IPv4Address

    def serialize(self) -> Mapping[str, Any]:
        values: dict[str, Any] = {}

        for field in fields(self):
            values[field.name] = getattr(self, field.name)

        return values
