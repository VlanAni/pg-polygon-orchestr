from dataclasses import dataclass


@dataclass(frozen=True)
class NodeConfig:
    cpu_limit: int
    ram_limit: str  # формат [число]m / [число]g
    os_name: str  # для разворачивания в докере надо использовать имя образа
    disk_limit: (
        str  # формат [число]m / [число]g (для докера этот параметр не учитывается)
    ) = ""
    name: str = ""
    connect_to_docker_default_net: bool = (
        False  # этот параметр будет учитываться только при развёртывании в докере
    )
    net_config_rights: bool = False
    ip_forwarding_on_node: bool = False
