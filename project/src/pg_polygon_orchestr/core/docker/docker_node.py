from typing import Any, Mapping

import docker
import docker.errors
import docker.models.images as dockerapi_images
import docker.models.containers as dockerapi_containers
import time
import uuid
import os
import typing

from ..configs import NodeConfig
from ..exception import docker_exceptions, common_exceptions
from ..abstract import Node, EntityRegistry, Volume
from . import docker_session
from ..meta import MountConfig, Type, EntityState, ExecResult, MountableType


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
        self.__clsession: docker_session.DockerClientSession = session
        self.__ditag: str = ""
        self.__state: EntityState = EntityState.NOT_DEPLOYED
        self.__dimg: dockerapi_images.Image | None = None
        self.__dcont: dockerapi_containers.Container | None = None
        self.__uuid: uuid.UUID = uuid.uuid4() if id is None else id
        self.__mounted: dict[str, MountConfig] = dict()
        self.__shrd_volumes: EntityRegistry = shared_volume_registry
        self.__real_name = str(self.__uuid)

    # ----- Интерфейсные методы

    def deploy(self, **options: str | list[MountConfig]) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.DEPLOYED):
            raise common_exceptions.EntityIsAlreadyDeployed(
                f"the node {self.__inf_name} is already deployed"
            )

        if "mount_configs" in options:
            mount_configs = options["mount_configs"]
            if isinstance(options["mount_configs"], list):
                mount_configs = typing.cast(list[MountConfig], mount_configs)
                self.__deploy(mount_configs=mount_configs)
            else:
                raise docker_exceptions.DockerDeployError(
                    f"mount_configs contains wrong data-types: {type(mount_configs)}"
                )
        else:
            self.__deploy()

    def clear(self) -> None:
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

    def get_type(self) -> Type:
        return Type.DOCKER

    def inf_name(self) -> str:
        return self.__inf_name

    def get_id(self) -> uuid.UUID:
        return self.__uuid

    def transform_to_mapping(self) -> Mapping[str, Any]:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.TryToSerializeRemovedEntity(
                f"the node {self.__inf_name} is removed"
            )

        return {
            "type": Type.DOCKER,
            "uuid": self.__uuid,
            "name": self.__inf_name,
            "state": self.__state,
            "mounted": self.__filter_mounted_to_serialize(),
            "config": self.__config,
        }

    def real_name(self) -> str:
        return self.__real_name

    def state(self) -> EntityState:
        return self.__state

    # ------ приватные коллбеки

    def __deploy(self, mount_configs: list[MountConfig] = []) -> None:
        if self.__dimg and self.__ditag:
            pass
        else:
            image_tag = f"{str(self.__uuid)}:v0"
            self.__ditag = image_tag
            try:
                image = self.__clsession.ask_to_build_image(  # type: ignore
                    config=self.__config, image_tag=image_tag  # type: ignore
                )

                self.__dimg = image
                self.__state = EntityState.DEPLOYED
            except docker_exceptions.ImageBuildError as err:
                raise docker_exceptions.DockerDeployError(
                    f"failed to build a docker image: {err}"
                ) from err

        try:
            for mnt_cfg in mount_configs:
                mnted = mnt_cfg.mounted

                if mnted.mtype() == MountableType.HOSTPATH:

                    if not os.path.exists(path=mnted.source()):
                        self.__mounted.clear()
                        docker_exceptions.DockerDeployError(
                            f"the path {mnted.source()} does not exists"
                        )

                elif mnted.mtype() == MountableType.VOLUME:
                    mnted = typing.cast(Volume, mnted)

                    if mnted.get_type() != Type.DOCKER:
                        self.__mounted.clear()
                        docker_exceptions.DockerDeployError(f"not a docker volume")

                    if mnted.state() != EntityState.DEPLOYED:
                        self.__mounted.clear()
                        docker_exceptions.DockerDeployError(f"not deployed volume")

                    search_result = self.__shrd_volumes.get_entity_by_id(
                        uuid=mnted.get_id()
                    )

                    if search_result is None:
                        self.__mounted.clear()
                        docker_exceptions.DockerDeployError(f"unknown docker volume")

                src = mnted.source()
                self.__mounted[src] = mnt_cfg

            container = self.__clsession.ask_to_create_a_container(  # type: ignore
                image=self.__dimg,  # type: ignore
                config=self.__config,  # type: ignore
                name=str(self.__uuid),
                mount_configs=mount_configs,
            )

            self.__dcont = container
        except docker_exceptions.ResourceCreationError as err:
            self.__mounted.clear()

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
        self.__mounted.clear()
        self.__state = EntityState.NOT_DEPLOYED

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
        self.__mounted.clear()
        self.__state = EntityState.REMOVED

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

    def share_container_id(self) -> str | None:
        if self.__dcont is None:
            return None

        self.__dcont.reload()
        return self.__dcont.id

    def docker_commit(self, pause: bool = True) -> tuple[dockerapi_images.Image, str]:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the node {self.__inf_name} is not deployed"
            )

        try:
            snapshot_repo = f"snapshot_{str(self.__uuid)}"
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

    def push_image_to_run(self, image: dockerapi_images.Image, image_tag: str) -> None:
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

    # ------ приватные проверки

    def __is_state_as_required(self, required: EntityState) -> bool:
        return self.__state is required

    def __filter_mounted_to_serialize(self) -> Mapping[str, typing.Any]:
        mounted_dump: dict[str, typing.Any] = dict()

        for mnt_src, mnt_cfg in self.__mounted.items():
            if mnt_cfg.mounted.mtype == MountableType.VOLUME:
                vol_obj = typing.cast(Volume, mnt_cfg.mounted)

                if vol_obj.state != EntityState.DEPLOYED:
                    continue
            elif mnt_cfg.mounted.mtype == MountableType.HOSTPATH:
                if not os.path.exists(mnt_src):
                    continue

            mounted_dump[mnt_src] = mnt_cfg

        return mounted_dump
