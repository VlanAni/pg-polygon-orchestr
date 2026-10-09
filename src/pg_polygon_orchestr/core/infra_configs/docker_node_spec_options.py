from dataclasses import dataclass, fields
import types
import typing

from ..serializable import Serializable, EasyDecodable

_DEFAULT_WORKDIR = "/app"
_DEFAULT_KEEPALIVE_COMMAND: tuple[str, ...] = ("tail", "-f", "/dev/null")


class DockerNodeConfigOptions(Serializable, EasyDecodable):

    def __init__(
        self,
        cap_add: list[str] | None = None,
        cap_drop: list[str] | None = None,
        environment: dict[str, str] | None = None,
        detach_from_default_bridge: bool = False,
        sysctls: dict[str, str] | None = None,
        device_write_bps: list[DeviceRateLimit] | None = None,
        device_read_bps: list[DeviceRateLimit] | None = None,
        entrypoint: str | list[str] | None = None,
        command: str | list[str] | None = None,
        privileged: bool = False,
        hostname: str | None = None,
        workdir: str | None = None,
        keep_image_command: bool = False,
    ) -> None:

        if cap_add and cap_drop and (overlap := set(cap_add) & set(cap_drop)):
            raise ValueError(
                f"capabilities listed in both caps_add and caps_drop: {overlap}"
            )

        if keep_image_command and (entrypoint or command):
            raise ValueError(
                "keep_image_command=True conflicts with passed" "entrypoint/command"
            )

        if isinstance(entrypoint, str) and command:
            raise ValueError("entrypoint in shell form will ignore the passed command")

        self.__cap_add: tuple[str, ...] | None = tuple(cap_add) if cap_add else None
        self.__cap_drop: tuple[str, ...] | None = tuple(cap_drop) if cap_drop else None

        self.__environment = (
            types.MappingProxyType(environment) if environment else None
        )

        self.__detach_from_default_bridge = detach_from_default_bridge
        self.__sysctls = types.MappingProxyType(sysctls) if sysctls else None

        self.__device_write_bps: tuple[DeviceRateLimit, ...] | None = (
            tuple(device_write_bps) if device_write_bps else None
        )

        self.__device_read_bps: tuple[DeviceRateLimit, ...] | None = (
            tuple(device_read_bps) if device_read_bps else None
        )

        self.__entrypoint: str | tuple[str, ...] | None = (
            entrypoint
            if isinstance(entrypoint, str)
            else tuple(entrypoint) if isinstance(entrypoint, list) else None
        )

        self.__command: str | tuple[str, ...] | None = (
            command
            if isinstance(command, str)
            else tuple(command) if isinstance(command, list) else None
        )

        self.__privileged = privileged
        self.__hostname = hostname
        self.__workdir = workdir
        self.__keep_image_command = keep_image_command

    @property
    def detach_from_default_bridge(self) -> bool:
        return self.__detach_from_default_bridge

    def to_host_config_kwargs(self) -> dict[str, typing.Any]:

        kwargs: dict[str, typing.Any] = {}

        if self.__cap_add:
            kwargs["cap_add"] = list(self.__cap_add)

        if self.__cap_drop:
            kwargs["cap_drop"] = list(self.__cap_drop)

        if self.__sysctls:
            kwargs["sysctls"] = dict(self.__sysctls)

        if self.__device_write_bps:
            kwargs["device_write_bps"] = [
                d.to_docker_dict() for d in self.__device_write_bps
            ]

        if self.__device_read_bps:
            kwargs["device_read_bps"] = [
                d.to_docker_dict() for d in self.__device_read_bps
            ]

        if self.__environment:
            kwargs["environment"] = dict(self.__environment)

        if self.__hostname:
            kwargs["hostname"] = self.__hostname

        kwargs["working_dir"] = (
            self.__workdir if self.__workdir is not None else _DEFAULT_WORKDIR
        )

        if self.__entrypoint:
            kwargs["entrypoint"] = (
                self.__entrypoint
                if isinstance(self.__entrypoint, str)
                else list(self.__entrypoint)
            )

        if self.__command:
            kwargs["command"] = (
                self.__command
                if isinstance(self.__command, str)
                else list(self.__command)
            )
        elif not self.__entrypoint and not self.__keep_image_command:
            kwargs["command"] = list(_DEFAULT_KEEPALIVE_COMMAND)

        kwargs["privileged"] = self.__privileged

        return kwargs

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        return {
            "cap_add": self.__cap_add,
            "cap_drop": self.__cap_drop,
            "environment": self.__environment,
            "detach_from_default_bridge": self.__detach_from_default_bridge,
            "sysctls": self.__sysctls,
            "device_write_bps": self.__device_write_bps,
            "device_read_bps": self.__device_read_bps,
            "entrypoint": self.__entrypoint,
            "command": self.__command,
            "privileged": self.__privileged,
            "hostname": self.__hostname,
            "workdir": self.__workdir,
            "keep_image_command": self.__keep_image_command,
        }

    @classmethod
    def from_dict(
        cls, data: typing.Mapping[str, typing.Any]
    ) -> DockerNodeConfigOptions:
        device_write_bps = data.get("device_write_bps")
        device_read_bps = data.get("device_read_bps")

        return cls(
            cap_add=data.get("cap_add"),
            cap_drop=data.get("cap_drop"),
            environment=data.get("environment"),
            detach_from_default_bridge=data.get("detach_from_default_bridge", False),
            sysctls=data.get("sysctls"),
            device_write_bps=(
                [DeviceRateLimit.from_dict(d) for d in device_write_bps]
                if device_write_bps
                else None
            ),
            device_read_bps=(
                [DeviceRateLimit.from_dict(d) for d in device_read_bps]
                if device_read_bps
                else None
            ),
            entrypoint=data.get("entrypoint", None),
            command=data.get("command", None),
            privileged=data.get("privileged", False),
            hostname=data.get("hostname"),
            workdir=data.get("workdir"),
            keep_image_command=data.get("keep_image_command", False),
        )


@dataclass(frozen=True)
class DeviceRateLimit(Serializable, EasyDecodable):
    device_path: str
    rate_bytes_per_sec: int

    def __post_init__(self):
        if self.rate_bytes_per_sec <= 0:
            raise ValueError(f"rate must be positive, got {self.rate_bytes_per_sec}")
        if not self.device_path.startswith("/dev/"):
            raise ValueError(
                f"device_path must be an absolute /dev/* path, got {self.device_path}"
            )

    def to_docker_dict(self) -> dict[str, str | int]:
        return {"Path": self.device_path, "Rate": self.rate_bytes_per_sec}

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    @classmethod
    def from_dict(cls, data: typing.Mapping[str, typing.Any]) -> DeviceRateLimit:
        return cls(
            device_path=data.get("device_path"),  # type: ignore
            rate_bytes_per_sec=data.get("rate_bytes_per_sec"),  # type: ignore
        )
