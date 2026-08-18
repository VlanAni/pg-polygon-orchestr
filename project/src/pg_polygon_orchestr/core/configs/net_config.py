from dataclasses import dataclass, fields
import typing

from ..serializable import Serializable


@dataclass(frozen=True)
class NetConfig(Serializable):
    """Класс для конфигурации сети

    `internal`: `bool` (если `True` - узлы в сети не могут обращаться к внешним ресурсам)\n
    `ipv4`: `bool` (если `True` - сеть поддерживает IPv4 (True по умолчанию))\n
    `ipv6`: `bool` (если `True` - сеть поддерживает IPv6 (False по умолчанию))\n
    `docker_net_driver`: `str` (указывает драйвер сети, который будет использован для создания сети Docker (по умолчанию "bridge"))\n

    Класс **иммутабельный**
    """

    internal: bool
    ipv4: bool = True
    ipv6: bool = False
    docker_net_driver: str = "bridge"

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        result: dict[str, typing.Any] = dict()

        for f in fields(self):
            f_name = f.name
            f_value = getattr(self, f_name)

            result[f_name] = f_value

        return result
