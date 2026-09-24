from dataclasses import dataclass

import typing

from ..serializable import Serializable, EasyDecodable

from . import mount, docker_mount_options


@dataclass(frozen=True)
class BindMountConfig(Serializable, EasyDecodable):
    host_mnt: mount.BindMount
    dst: str
    dock_mnt_opts: docker_mount_options.DockerBindMountOpts = (
        docker_mount_options.DockerBindMountOpts()
    )

    @classmethod
    def from_dict(cls, data: typing.Mapping[str, typing.Any]) -> typing.Self:
        return cls(
            host_mnt=mount.BindMount.from_dict(data=data["host_mnt"]),  # type: ignore
            dst=data["dst"],  # type: ignore
            dock_mnt_opts=docker_mount_options.DockerBindMountOpts.from_dict(
                data=data["dock_mnt_opts"]  # type: ignore
            ),
        )
