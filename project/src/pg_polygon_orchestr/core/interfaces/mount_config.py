from dataclasses import dataclass

from .volume import Volume


@dataclass(frozen=True)
class MountConfig:
    volume: Volume
    mount_path: str
    read_only: bool
