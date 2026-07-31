import docker.models.volumes as docker_volumes
from dataclasses import dataclass


@dataclass(frozen=True)
class VolumeDesc:
    volume_obj: docker_volumes.Volume
    mount_path: str
    read_only: bool
    delete_on_destroy: bool
