from dataclasses import dataclass


@dataclass(frozen=True)
class NodeConfig:
    os: str
    cpu_limit: int
    mem_limit: str
    ip_forwarding: bool = False
    net_settings_roots: bool = False
    storage_limit: str = ""
    program_to_execute: str = ""
    connect_to_docker_default: bool = True
