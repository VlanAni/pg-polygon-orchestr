from dataclasses import dataclass
import typing

from ..common_interfaces import Config
from .docker_node_spec_options import DockerNodeConfigOptions


@dataclass
class NodeConfig(Config):
    base_image: str
    cpu_limit: int | None = None
    mem_limit: str | None = None
    docker_params: DockerNodeConfigOptions = DockerNodeConfigOptions()

    @classmethod
    def from_dict(cls, data: typing.Mapping[str, typing.Any]) -> NodeConfig:
        return cls(
            base_image=data.get("base_image"),  # type: ignore
            cpu_limit=data.get("cpu_limit"),  # type: ignore
            mem_limit=data.get("mem_limit"),  # type: ignore
            docker_params=DockerNodeConfigOptions.from_dict(data=data.get("docker_params")),  # type: ignore
        )
