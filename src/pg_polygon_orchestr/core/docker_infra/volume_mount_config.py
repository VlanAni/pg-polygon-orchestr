from dataclasses import dataclass, fields
from typing import Any, Mapping

from . import docker_volume
from ..serializable import Serializable


@dataclass(frozen=True)
class VolumeMountConfig(Serializable):

    volume: docker_volume.DockerVolume
    dst: str
    no_copy: bool = False
    ro: bool = False
    subpath: str | None = None

    def serialize(self) -> Mapping[str, Any]:
        result: dict[str, Any] = {}

        for field in fields(self):
            value = getattr(self, field.name)

            if isinstance(value, docker_volume.DockerVolume):
                result[field.name] = value.uuid
            else:
                result[field.name] = value

        return result
