from dataclasses import dataclass, fields
import typing

from .docker_network_spec_options import DockerNetworkConfigOptions
from ..common_interfaces import Config


@dataclass(frozen=True)
class NetConfig(Config):

    docker_net_options: DockerNetworkConfigOptions = DockerNetworkConfigOptions()

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        result: dict[str, typing.Any] = dict()

        for f in fields(self):
            f_name = f.name
            f_value = getattr(self, f_name)

            result[f_name] = f_value

        return result

    @classmethod
    def from_dict(cls, data: typing.Mapping[str, typing.Any]) -> typing.Self:
        docker_node_options = DockerNetworkConfigOptions.from_dict(
            data=data["docker_net_options"]
        )

        return cls(docker_net_options=docker_node_options)
