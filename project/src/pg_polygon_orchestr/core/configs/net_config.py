from dataclasses import dataclass, fields
import typing

from ..serializable import Serializable


@dataclass(frozen=True)
class NetConfig(Serializable):
    internal: bool
    ipv4: bool = True
    ipv6: bool = False
    docker_net_driver: str = "bridge"

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        result: dict[str, typing.Any] = dict()

        for f in fields(self):
            f_name = f.name
            f_value = getattr(self, f_name)

            result[f_name] = f_value

        return result
