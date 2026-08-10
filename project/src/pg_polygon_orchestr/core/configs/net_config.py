from dataclasses import dataclass, asdict
import typing


@dataclass(frozen=True)
class NetConfig:
    internal: bool
    ipv4: bool = True
    ipv6: bool = False
    docker_net_driver: str = "bridge"

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        return asdict(self)
