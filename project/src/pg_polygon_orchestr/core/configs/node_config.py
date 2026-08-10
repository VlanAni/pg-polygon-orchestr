from dataclasses import dataclass, asdict
import typing


@dataclass(frozen=True)
class NodeConfig:
    os: str
    cpu_limit: int
    mem_limit: str
    ip_forwarding: bool = False
    net_settings_roots: bool = False
    storage_limit: str = ""
    connect_to_docker_default: bool = True

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        return asdict(self)
