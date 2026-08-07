from dataclasses import dataclass


@dataclass(frozen=True)
class MountConfig:
    volume_host_path: str
    mount_path: str
    read_only: bool
