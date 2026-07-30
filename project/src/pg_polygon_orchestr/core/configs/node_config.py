from dataclasses import dataclass


@dataclass(frozen=True)
class NodeConfig:
    cpu_limit: int
    ram_limit: str  # for docker use this format [number]m / [number]g
    disk_limit: str  # for docker use this format [number]m / [number]g
    os_name: str  # for docker use docker's image name
    connect_to_docker_default_net: bool = False
    docker_net_admin_cap: bool = False
