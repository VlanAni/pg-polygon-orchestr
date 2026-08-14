from dataclasses import dataclass, fields
import typing

from ..serializable import Serializable


@dataclass(frozen=True)
class NodeConfig(Serializable):
    os: str
    cpu_limit: int
    mem_limit: str
    ip_forwarding: bool = False
    net_settings_roots: bool = False
    storage_limit: str = ""
    connect_to_docker_default: bool = True

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        result: dict[str, typing.Any] = dict()

        for f in fields(self):
            f_name = f.name
            f_value = getattr(self, f_name)

            result[f_name] = f_value

        return result
