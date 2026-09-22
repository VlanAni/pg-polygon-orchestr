from dataclasses import dataclass, fields
import typing

from ..serializable import Serializable
from .docker_node_spec_options import DockerNodeConfigOptions


@dataclass
class NodeConfig(Serializable):
    os: str
    cpu_limit: int
    mem_limit: str
    docker_params: DockerNodeConfigOptions = DockerNodeConfigOptions()

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    @classmethod
    def from_dict(cls, data: typing.Mapping[str, typing.Any]) -> NodeConfig:
        return cls(
            os=data.get("os"),  # type: ignore
            cpu_limit=data.get("cpu_limit"),  # type: ignore
            mem_limit=data.get("mem_limit"),  # type: ignore
            docker_params=DockerNodeConfigOptions.from_dict(data=data.get("docker_params")),  # type: ignore
        )
