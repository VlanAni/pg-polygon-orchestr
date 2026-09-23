from dataclasses import dataclass
import ipaddress

from ..serializable import Serializable


@dataclass(frozen=True)
class ConnectionInfo(Serializable):
    subnet_label: str
    addr: ipaddress.IPv4Address
