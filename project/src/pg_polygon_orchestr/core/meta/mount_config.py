from dataclasses import dataclass, fields
import typing

from ..serializable import Serializable

from .mounted import Mountable


@dataclass(frozen=True)
class MountConfig(Serializable):
    """Конфигурация для монтирования ресурсов

    `mounted`: `Mountable` - объект, который нужно смонтировать (`Volume` / `HostPathDesc`)\n
    `mount_path`: `str` - куда монтировать сущность внутри контейнера\n
    `read_only`: `bool` - смонтированный ресурс доступен только для чтения

    """

    mounted: Mountable
    mount_path: str
    read_only: bool

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        result: dict[str, typing.Any] = dict()

        for f in fields(self):
            f_name = f.name
            f_value = getattr(self, f_name)

            if isinstance(f_value, Mountable):
                result[f_name] = {"type": f_value.mtype(), "source": f_value.source()}
            else:
                result[f_name] = f_value

        return result
