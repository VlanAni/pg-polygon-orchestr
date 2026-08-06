from dataclasses import dataclass


@dataclass(frozen=True)
class NetConfig:
    internal: bool
    ipv4: bool = True
    ipv6: bool = False
    docker_net_driver: str = "bridge"
