from dataclasses import dataclass, fields
from typing import Any, Mapping

from ..serializable import Serializable


@dataclass(frozen=True)
class MountConfig(Serializable):
    volume_host_path: str
    mount_path: str
    read_only: bool

    def serialize(self) -> Mapping[str, Any]:
        result: dict[str, Any] = dict()

        for f in fields(self):
            f_name = f.name
            f_value = getattr(self, f_name)

            result[f_name] = f_value

        return result
