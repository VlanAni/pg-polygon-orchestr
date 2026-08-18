from dataclasses import dataclass, field, InitVar, fields
import typing

from ..serializable import Serializable


@dataclass
class VolumeConfig(Serializable):
    """Конфиг для Volume'ов

    `docker_volume_driver`: `str` - драйвер для Docker Volume'а\n
    `path_on_host`: `str` - путь к тому на хосте (используется для виртуальных машин)\n
    `docker_driver_options`: `dict[str, str]` - опции драйвера Docker Volume'а. Имеют такой же формат, как и в `docker-py`\n
    Класс является **иммутабельным**

    """

    docker_volume_driver: str
    path_on_host: str = ""
    docker_driver_opts: InitVar[dict[str, str] | None] = None  # type: ignore
    _docker_driver_opts: dict[str, str] = field(init=False, repr=False)

    def __post_init__(
        self, docker_driver_opts: dict[str, str] | None  # type: ignore
    ) -> None:
        self._docker_driver_opts = (
            {} if docker_driver_opts is None else docker_driver_opts.copy()
        )

    @property
    def docker_driver_options(self) -> dict[str, str]:
        return self._docker_driver_opts.copy()

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        result: dict[str, typing.Any] = {}

        for f in fields(self):
            if f.name.startswith("_"):
                continue
            value = getattr(self, f.name)
            result[f.name] = value.copy() if isinstance(value, dict) else value

        result["docker_driver_opts"] = self.docker_driver_options
        return result
