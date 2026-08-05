from dataclasses import dataclass


@dataclass(frozen=True)
class NetConfig:
    ipv4: bool
    ipv6: bool
    internal: bool
    docker_net_driver: str = ""
