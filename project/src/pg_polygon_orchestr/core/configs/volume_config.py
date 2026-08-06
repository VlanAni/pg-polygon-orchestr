from dataclasses import dataclass, field, InitVar


@dataclass
class VolumeConfig:
    path_on_host: str = ""
    docker_volume_driver: str = ""
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
