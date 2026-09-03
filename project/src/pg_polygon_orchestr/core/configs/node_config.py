from dataclasses import dataclass, fields, InitVar, field
import typing

from ..serializable import Serializable


@dataclass
class NodeConfig(Serializable):
    # общая конфигурация
    os: str
    cpu_limit: int
    mem_limit: str
    storage_limit: str = ""

    # конфигурации для докера
    docker_linux_caps_add: InitVar[list[str]] = []
    docker_linux_caps_drop: InitVar[list[str]] = []
    docker_container_env: InitVar[dict[str, str]] = {}
    docker_default_bridge_connection: bool = True
    docker_container_ip_forwarding: bool = False

    __docker_linux_caps_add: list[str] = field(init=False, repr=False)
    __docker_linux_caps_drop: list[str] = field(init=False, repr=False)
    __docker_container_env: dict[str, str] = field(init=False, repr=False)

    def __post_init__(
        self,
        docker_linux_caps_add: list[str],
        docker_linux_caps_drop: list[str],
        docker_container_env: dict[str, str],
    ):
        self.__docker_linux_caps_add = docker_linux_caps_add.copy()
        self.__docker_linux_caps_drop = docker_linux_caps_drop.copy()
        self.__docker_container_env = docker_container_env.copy()

    @property
    def docker_linux_cap_add(self):
        return self.__docker_linux_caps_add.copy()

    @property
    def docker_linux_cap_drop(self):
        return self.__docker_linux_caps_drop.copy()

    @property
    def docker_environment(self):
        return self.__docker_container_env.copy()

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        result: dict[str, typing.Any] = dict()

        for f in fields(self):
            f_name = f.name
            f_value = getattr(self, f_name)

            if f_name.startswith("_"):
                f_name = f_name.split("__")[-1]

            result[f_name] = (
                f_value.copy()
                if isinstance(f_value, dict) or isinstance(f_value, list)
                else f_value
            )

        return result
