from dataclasses import dataclass, field, InitVar, fields
import typing

from ..serializable import Serializable


@dataclass()
class VolumeConfig(Serializable):
    path_on_host: str = ""

    # параметры для докера
    docker_volume_driver: str = "local"
    docker_driver_opts: InitVar[dict[str, str]] = {}
    __docker_driver_opts: dict[str, str] = field(init=False, repr=False)

    def __post_init__(self, docker_driver_opts: dict[str, str]) -> None:
        self.__docker_driver_opts = docker_driver_opts.copy()

    @property
    def docker_driver_options(self) -> dict[str, str]:
        return self.__docker_driver_opts.copy()

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        result: dict[str, typing.Any] = {}

        for f in fields(self):
            f_name = f.name
            value = getattr(self, f_name)

            if f_name.startswith("_"):
                f_name = f_name.split("__")[-1]

            result[f_name] = value.copy() if isinstance(value, dict) else value

        return result
