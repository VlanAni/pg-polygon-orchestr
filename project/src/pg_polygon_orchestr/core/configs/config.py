from dataclasses import dataclass


@dataclass
class Config:
    cpu_limit: int
    ram_limit: str  # for docker use this format [number]m / [number]g
    disk_limit: str  # for docker use this format [number]m / [number]g
    os_name: str  # for docker use docker's image name
