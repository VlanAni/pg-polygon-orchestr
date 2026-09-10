from dataclasses import dataclass, fields
import ipaddress
from typing import Any, Mapping

from ..serializable import Serializable


@dataclass(frozen=True)
class SubnetInfo(Serializable):
    label: str
    subnet: ipaddress.IPv4Network
    gateway: ipaddress.IPv4Address

    def serialize(self) -> Mapping[str, Any]:
        return {field.name: getattr(self, field.name) for field in fields(SubnetInfo)}
