from dataclasses import dataclass, fields
import typing

from ..serializable import Serializable


@dataclass(frozen=True)
class NodeConfig(Serializable):
    """Конфиг для узла инфраструктуры

    `os`: `str` - операционная система узла (для Docker - название базового образа с ОС)\n
    `cpu_limit`: `int` - процессорные единицы (сколько ядер может использовать узел)\n
    `mem_limit`: `str` - лимит на память (формат `число[g/m]`)\n
    `ip_forwarding`: `bool` = False - включение на узле пересылку ip-пакетов\n
    `net_settings_roots`: `bool` = False - предоставить ли capabilities для сетевой настройки ноды после запуска (к примеру, таблиц маршрутизации)\n
    `connect_to_docker_default`: `bool` = True - флаг подключения узла к дефолтной сети Docker'а\n
    Класс **иммутабельный**

    """

    os: str
    cpu_limit: int
    mem_limit: str
    ip_forwarding: bool = False
    net_settings_roots: bool = False
    storage_limit: str = ""
    connect_to_docker_default: bool = True

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        result: dict[str, typing.Any] = dict()

        for f in fields(self):
            f_name = f.name
            f_value = getattr(self, f_name)

            result[f_name] = f_value

        return result
