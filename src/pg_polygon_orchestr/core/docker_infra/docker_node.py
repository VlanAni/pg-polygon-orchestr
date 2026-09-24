from typing import Any, Mapping

import docker
import docker.errors
import docker.models.images as dockerapi_images
import docker.models.containers as dockerapi_containers
import docker.types as dockerapi_types
import time
import uuid
import typing

from ..infra_configs import NodeConfig
from ..infra import Node
from ..exception import docker_exceptions, common_exceptions
from ..common_interfaces import EntityRegistry
from ..docker_utils import docker_session
from ..common_types import (
    InfraType,
    EntityState,
    ExecResult,
)
from . import docker_network as dnet
from . import volume_mount_config as vmc
from ..mount import BindMountConfig


class DockerNode(Node):
    def __init__(
        self,
        name: str,
        config: NodeConfig,
        session: docker_session.DockerClientSession,
        shared_volume_registry: EntityRegistry,
        id: uuid.UUID | None = None,
    ) -> None:

        self.__inf_name = name
        self.__config = config
        self.__uuid: uuid.UUID = uuid.uuid4() if id is None else id
        self.__state: EntityState = EntityState.NOT_DEPLOYED

        self.__clsession: docker_session.DockerClientSession = session
        self.__ditag: str = ""
        self.__dimg: dockerapi_images.Image | None = None
        self.__dcont: dockerapi_containers.Container | None = None

        self.__bind_mounted: list[BindMountConfig] = list()
        self.__mounted_volumes: list[vmc.VolumeMountConfig] = list()
        self.__conn_nets: list[dnet.DockerNetwork] = []

    # ----- Интерфейсные методы

    def deploy(
        self, **options: list[BindMountConfig] | list[vmc.VolumeMountConfig]
    ) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.DEPLOYED):
            raise common_exceptions.EntityIsAlreadyDeployed(
                f"the node {self.__inf_name} is already deployed"
            )

        bind_mount_configs: list[BindMountConfig]

        if "bind_mount_configs" in options:
            raw_bind_mounts = options["bind_mount_configs"]
            try:
                if not _validate_bind_mounts(raw_bind_mounts):
                    raise docker_exceptions.DockerDeployError(
                        "not a list of BindMountConfig"
                    )
            except Exception as err:
                raise docker_exceptions.DockerDeployError(
                    "not a list of BindMountConfig"
                ) from err
            bind_mount_configs = raw_bind_mounts
        else:
            bind_mount_configs = []

        volume_mount_configs: list[vmc.VolumeMountConfig]

        if "volume_mount_configs" in options:
            raw_volume_mounts = options["volume_mount_configs"]
            try:
                if not _validate_volume_mounts(raw_volume_mounts):
                    raise docker_exceptions.DockerDeployError(
                        "not a list of VolumeMountConfig"
                    )
            except Exception as err:
                raise docker_exceptions.DockerDeployError(
                    "not a list of VolumeMountConfig"
                ) from err
            volume_mount_configs = raw_volume_mounts
        else:
            volume_mount_configs = []

        self.__deploy(
            bind_mount_configs=bind_mount_configs,
            volume_mount_configs=volume_mount_configs,
        )

    def undeploy(self) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the node {self.__inf_name} is not deployed"
            )

        self.__clear()

    def start(self) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the node {self.__inf_name} is not deployed"
            )

        self.__start()

    def stop(self, timeout: int) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the node {self.__inf_name} is not deployed"
            )

        self.__stop(timeout=timeout)

    def exec(self, command: str) -> ExecResult:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the node {self.__inf_name} is not deployed"
            )

        return self.__exec(command=command)

    def update(self, new_config: NodeConfig) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__inf_name} is removed"
            )

        self.__update(new_config=new_config)

    def remove(self) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__inf_name} is removed"
            )

        self.__remove()

    @property
    def type(self) -> InfraType:
        return InfraType.DOCKER

    @property
    def inf_name(self) -> str:
        return self.__inf_name

    @property
    def uuid(self) -> uuid.UUID:
        return self.__uuid

    def serialize(self) -> Mapping[str, Any]:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.TryToSerializeRemovedEntity(
                f"the node {self.__inf_name} is removed"
            )

        return {
            "type": InfraType.DOCKER,
            "uuid": self.__uuid,
            "name": self.__inf_name,
            "state": self.__state,
            "bind_mount_configs": self.__bind_mounted,
            "volume_mount_configs": _filter_volumes(vmcs=self.__mounted_volumes),
            "config": self.__config,
        }

    @property
    def real_name(self) -> str:
        return str(self.__uuid)

    @property
    def state(self) -> EntityState:
        return self.__state

    # ------ приватные коллбеки

    def __deploy(
        self,
        bind_mount_configs: list[BindMountConfig] = [],
        volume_mount_configs: list[vmc.VolumeMountConfig] = [],
    ) -> None:
        if self.__dimg and self.__ditag:

            pass

        else:
            image_tag = f"{str(self.__uuid)}:v0"
            self.__ditag = image_tag
            try:

                if self.__config is None:
                    raise docker_exceptions.DockerDeployError(f"the config is None")

                image = self.__clsession.ask_to_build_image(
                    config=self.__config, image_tag=image_tag
                )

                self.__dimg = image
                self.__state = EntityState.DEPLOYED
            except docker_exceptions.ImageBuildError as err:
                raise docker_exceptions.DockerDeployError(
                    f"failed to build a docker image: {err}"
                ) from err

        try:

            docker_mounts: list[dockerapi_types.Mount] = []

            for bmc in bind_mount_configs:
                docker_mounts.append(
                    dockerapi_types.Mount(
                        target=bmc.dst,
                        source=bmc.host_mnt.src,
                        type="bind",
                        read_only=bmc.dock_mnt_opts.ro,
                    )
                )

            for vmc in volume_mount_configs:
                docker_mounts.append(
                    dockerapi_types.Mount(
                        target=vmc.dst,
                        source=vmc.volume.real_name,
                        type="volume",
                        read_only=vmc.ro,
                        no_copy=vmc.no_copy,
                        subpath=vmc.subpath,
                    )
                )

            container = self.__clsession.ask_to_create_a_container(  # type: ignore
                image=self.__dimg,  # type: ignore
                config=self.__config,  # type: ignore
                name=str(self.__uuid),
                mounts=docker_mounts,
            )

            self.__dcont = container
            self.__bind_mounted = bind_mount_configs.copy()
            self.__mounted_volumes = volume_mount_configs.copy()

        except docker_exceptions.ResourceCreationError as err:

            self.__bind_mounted.clear()
            self.__mounted_volumes.clear()

            raise docker_exceptions.DockerDeployError(
                f"failed to create a docker container for the node {self.__inf_name}"
            ) from err

        self.__state = EntityState.DEPLOYED

    def __clear(self) -> None:
        try:
            if self.__dcont is not None:
                self.__dcont.remove()
            self.__clsession.ask_to_delete_image(image=self.__ditag)
        except docker.errors.APIError as err:
            raise docker_exceptions.DockerClearError(
                f"failed to remove node's {self.__inf_name} container"
            ) from err
        except docker_exceptions.FailedToDeleteAnImage as err:
            raise docker_exceptions.DockerClearError(
                f"failed to remove node' {self.__inf_name} image {self.__ditag}"
            ) from err

        self.__dcont = None
        self.__ditag = ""
        self.__dimg = None
        self.__bind_mounted.clear()
        self.__mounted_volumes.clear()
        self.__state = EntityState.NOT_DEPLOYED

        for net in self.__conn_nets:
            if self.__is_state_as_required(required=EntityState.DEPLOYED):
                net._free_address_of_not_deployed_node(  # pyright: ignore[reportPrivateUsage]
                    node=self
                )

        self.__conn_nets = []

    def __remove(self) -> None:
        if self.__is_state_as_required(required=EntityState.DEPLOYED):
            try:
                if self.__dcont is not None:
                    self.__dcont.remove(force=True)
                self.__clsession.ask_to_delete_image(image=self.__ditag)
            except docker.errors.APIError as err:
                raise docker_exceptions.DockerClearError(
                    f"failed to force remove node's {self.__inf_name} container"
                ) from err
            except docker_exceptions.FailedToDeleteAnImage as err:
                raise docker_exceptions.DockerClearError(
                    f"failed to force remove node's {self.__inf_name} image {self.__ditag}"
                ) from err

        self.__dcont = None
        self.__ditag = ""
        self.__dimg = None
        self.__config = None
        self.__bind_mounted.clear()
        self.__state = EntityState.REMOVED

        for net in self.__conn_nets:
            if self.__is_state_as_required(required=EntityState.DEPLOYED):
                net._free_address_of_not_deployed_node(  # pyright: ignore[reportPrivateUsage]
                    node=self
                )

        self.__conn_nets = []

    def __start(self) -> None:
        try:
            self.__dcont.reload()  # type: ignore

            if self.__dcont.status == "running":  # type: ignore
                raise docker_exceptions.ContainerAlreadyRunning(
                    f"the node {self.__inf_name} already running with its container"
                )

            self.__dcont.start()  # type: ignore
        except docker.errors.APIError as err:
            raise docker_exceptions.DockerContStartError(
                f"failed to start the container {self.__dcont.name}: {err}"  # type: ignore
            ) from err

    def __stop(self, timeout: int) -> None:
        try:
            self.__dcont.reload()  # type: ignore

            if self.__dcont.status != "running":  # type: ignore
                raise docker_exceptions.ContainerAlreadyStopped(
                    f"the node {self.__inf_name} is already stopped"
                )

            self.__dcont.stop(timeout=timeout)  # type: ignore
        except docker.errors.APIError as err:
            raise docker_exceptions.DockerContStopError(
                f"cannot stop the container {self.__dcont.name}: {err}"  # type: ignore
            ) from err

    def __exec(self, command: str) -> ExecResult:
        try:
            self.__dcont.reload()  # type: ignore

            if self.__dcont.status != "running":  # type: ignore
                raise docker_exceptions.ExecOnContainerError(
                    f"the node {self.__inf_name} is stopped"
                )

            start = time.perf_counter_ns()
            result = self.__dcont.exec_run(command, demux=True)  # type: ignore
            end = time.perf_counter_ns()

            exit_code = result.exit_code
            stdout, stderr = result.output
            execution_time = end - start

            return ExecResult(
                exit_code,
                stdout=stdout.decode(encoding="utf-8") if stdout is not None else "",  # type: ignore
                stderr=stderr.decode(encoding="utf-8") if stderr is not None else "",  # type: ignore
                execution_time=execution_time,
            )
        except docker.errors.APIError as err:

            raise docker_exceptions.ExecOnContainerError(
                f"cannot execute the command {command} on the container {self.__dcont.name}"  # type: ignore
            ) from err

    def __update(self, new_config: NodeConfig) -> None:
        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            self.__config = new_config
        else:
            try:
                self.__dcont.update(  # type: ignore
                    mem_limit=new_config.mem_limit,  # type: ignore
                    cpu_period=100000,
                    cpu_quota=new_config.cpu_limit * 100000,  # type: ignore
                )

                self.__config = new_config

            except docker.errors.APIError as err:
                raise docker_exceptions.UpdateContainerConfError(
                    f"server returns an error: {err}"
                ) from err

    # ------ докер-специфичные функции (пользователю они не нужны)

    def _docker_container_id(self) -> str:
        return self.__dcont.id  # type: ignore

    def _docker_commit(self, pause: bool = True) -> tuple[dockerapi_images.Image, str]:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the node {self.__inf_name} is not deployed"
            )

        try:
            snapshot_repo = f"snapshot_{str(self.real_name)}"
            snapshot_tag = "v0"
            return (
                self.__dcont.commit(  # type: ignore
                    repository=snapshot_repo, tag=snapshot_tag, pause=pause
                ),
                f"{snapshot_repo}:{snapshot_tag}",
            )
        except docker.errors.APIError as err:
            raise docker_exceptions.FailedToCommit(
                f"failed to commit the container {self.__inf_name}"
            ) from err

    def _push_image_to_run(self, image: dockerapi_images.Image, image_tag: str) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.DEPLOYED):
            raise common_exceptions.EntityIsAlreadyDeployed(
                f"the node {self.__inf_name} is already deployed"
            )

        self.__dimg = image
        self.__ditag = image_tag

    def _push_connected_network(self, network: dnet.DockerNetwork) -> None:
        self.__conn_nets.append(network)

    # ------ приватные проверки

    def __is_state_as_required(self, required: EntityState) -> bool:
        return self.__state is required


def _filter_volumes(vmcs: list[vmc.VolumeMountConfig]) -> list[vmc.VolumeMountConfig]:
    filtered_volumes: list[vmc.VolumeMountConfig] = []

    for vmc in vmcs:
        if vmc.volume.state == EntityState.DEPLOYED:
            filtered_volumes.append(vmc)

    return filtered_volumes


def _validate_bind_mounts(value: Any) -> typing.TypeGuard[list[BindMountConfig]]:
    if not _is_list_of(value, BindMountConfig):
        raise TypeError(f"'bind_mounts' must be list[MountConfig], but: {value!r}")
    return True


def _validate_volume_mounts(
    value: Any,
) -> typing.TypeGuard[list[vmc.VolumeMountConfig]]:
    if not _is_list_of(value, vmc.VolumeMountConfig):
        raise TypeError(
            f"'volume_mounts' must be list[VolumeMountConfig], but: {value!r}"
        )
    return True


def _is_list_of(value: typing.Any, item_type: type) -> bool:
    if isinstance(value, list):
        return all(isinstance(item, item_type) for item in value)  # type: ignore

    return False
