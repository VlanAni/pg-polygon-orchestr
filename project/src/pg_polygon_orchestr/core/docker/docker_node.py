from typing import Any, Mapping

import docker
import docker.errors
import docker.models.images as docker_images
import docker.models.containers as docker_containers
import time
import uuid

from ..configs import NodeConfig
from ..exception import docker_exceptions, common_exceptions
from ..abstract import Node, EntityRegistry
from . import docker_session
from ..meta import MountConfig, Type, EntityState, ExecResult


class DockerNode(Node):
    def __init__(
        self,
        name: str,
        config: NodeConfig,
        session: docker_session.DockerClientSession,
        shared_volume_registry: EntityRegistry,
        id: uuid.UUID | None = None,
    ) -> None:
        self.__name = name
        self.__config = config
        self.__shared_client_session: docker_session.DockerClientSession = session
        self.__image_name: str = ""
        self.__state: EntityState = EntityState.NOT_DEPLOYED
        self.__docker_image: docker_images.Image | None = None
        self.__docker_container: docker_containers.Container | None = None
        self.__uuid: uuid.UUID = uuid.uuid4() if id is None else id
        self.__mounted_volumes: dict[uuid.UUID, MountConfig] = dict()
        self.__infrastructure_volumes: EntityRegistry = shared_volume_registry
        self.__provider_name = str(self.__uuid)

    # ----- Интерфейсные методы

    def deploy(self, **options: str) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.DEPLOYED):
            raise common_exceptions.EntityIsAlreadyDeployed(
                f"the node {self.__name} is already deployed"
            )

        self.__deploy()

    def clear(self) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the node {self.__name} is not deployed"
            )

        self.__clear()

    def start(self, mount_configs: list[MountConfig] = []) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the node {self.__name} is not deployed"
            )

        self.__start(mount_configs=mount_configs)

    def stop(self, timeout: int) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the node {self.__name} is not deployed"
            )

        self.__stop(timeout=timeout)

    def exec(self, command: str) -> ExecResult:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the node {self.__name} is not deployed"
            )

        return self.__exec(command=command)

    def update(self, new_config: NodeConfig) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__name} is removed"
            )

        self.__update(new_config=new_config)

    def remove(self) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__name} is removed"
            )

        self.__remove()

    def get_type(self) -> Type:
        return Type.DOCKER

    def get_name(self) -> str:
        return self.__name

    def get_id(self) -> uuid.UUID:
        return self.__uuid

    def transform_to_mapping(self) -> Mapping[str, Any]:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.TryToSerializeRemovedEntity(
                f"the node {self.__name} is removed"
            )

        return {
            "type": Type.DOCKER,
            "uuid": self.__uuid,
            "name": self.__name,
            "state": self.__state,
            "volumes": {
                str(vol_id): mount_cfg
                for vol_id, mount_cfg in self.__mounted_volumes.items()
            },
            "config": self.__config,
        }

    def get_provider_path(self) -> str:
        return self.__provider_name

    # ------ приватные коллбеки

    def __deploy(self) -> None:
        image_tag = f"{str(self.__uuid)}:v0"
        self.__image_name = image_tag
        try:
            image = self.__shared_client_session.ask_to_build_image(  # type: ignore
                config=self.__config, image_tag=image_tag  # type: ignore
            )

            self.__docker_image = image
            self.__state = EntityState.DEPLOYED
        except docker_exceptions.ImageBuildError as err:
            raise docker_exceptions.DockerDeployError(
                f"failed to build a docker image: {err}"
            ) from err

    def __clear(self) -> None:
        try:
            if self.__docker_container is not None:
                self.__docker_container.remove()
            self.__shared_client_session.ask_to_delete_image(image=self.__image_name)
        except docker.errors.APIError as err:
            raise docker_exceptions.DockerClearError(
                f"failed to remove node's {self.__name} container"
            ) from err
        except docker_exceptions.FailedToDeleteAnImage as err:
            raise docker_exceptions.DockerClearError(
                f"failed to remove node' {self.__name} image {self.__image_name}"
            ) from err

        self.__docker_container = None
        self.__image_name = ""
        self.__docker_image = None
        self.__mounted_volumes.clear()
        self.__state = EntityState.NOT_DEPLOYED

    def __remove(self) -> None:
        if self.__is_state_as_required(required=EntityState.DEPLOYED):
            try:
                if self.__docker_container is not None:
                    self.__docker_container.remove(force=True)
                self.__shared_client_session.ask_to_delete_image(
                    image=self.__image_name
                )
            except docker.errors.APIError as err:
                raise docker_exceptions.DockerClearError(
                    f"failed to force remove node's {self.__name} container"
                ) from err
            except docker_exceptions.FailedToDeleteAnImage as err:
                raise docker_exceptions.DockerClearError(
                    f"failed to force remove node's {self.__name} image {self.__image_name}"
                ) from err

        self.__docker_container = None
        self.__image_name = ""
        self.__docker_image = None
        self.__config = None
        self.__mounted_volumes.clear()
        self.__state = EntityState.REMOVED

    def __start(self, mount_configs: list[MountConfig] = []) -> None:
        if self.__docker_container is None:
            try:
                for mnt_cfg in mount_configs:
                    try:
                        volume_id = uuid.UUID(mnt_cfg.volume_host_path)
                    except Exception:
                        raise docker_exceptions.DockerContStartError(
                            f"the volume {mnt_cfg.volume_host_path} is not known"
                        )

                    search_result = self.__infrastructure_volumes.get_entity_by_id(
                        uuid=volume_id
                    )
                    if search_result is None:
                        self.__mounted_volumes.clear()

                        raise docker_exceptions.DockerContStartError(
                            f"the volume {mnt_cfg.volume_host_path} is not known"
                        )
                    else:
                        self.__mounted_volumes[search_result.get_id()] = mnt_cfg

                container = self.__shared_client_session.ask_to_create_a_container(  # type: ignore
                    image=self.__docker_image,  # type: ignore
                    config=self.__config,  # type: ignore
                    name=str(self.__uuid),
                    mount_configs=mount_configs,
                )

                self.__docker_container = container
            except docker_exceptions.ResourceCreationError as err:
                self.__mounted_volumes.clear()

                raise docker_exceptions.DockerContStartError(
                    f"failed to create a docker container for the node {self.__name}"
                ) from err

        else:
            try:
                self.__docker_container.reload()

                if self.__docker_container.status == "running":
                    raise docker_exceptions.ContainerAlreadyRunning(
                        f"the node {self.__name} already running with its container"
                    )

                self.__docker_container.start()
            except docker.errors.APIError as err:
                raise docker_exceptions.DockerContStartError(
                    f"failed to start the container {self.__docker_container.name}: {err}"
                ) from err

    def __stop(self, timeout: int) -> None:
        if self.__docker_container is not None:
            try:
                self.__docker_container.reload()

                if self.__docker_container.status != "running":
                    raise docker_exceptions.ContainerAlreadyStopped(
                        f"the node {self.__name} is already stopped"
                    )

                self.__docker_container.stop(timeout=timeout)
            except docker.errors.APIError as err:
                raise docker_exceptions.DockerContStopError(
                    f"cannot stop the container {self.__docker_container.name}: {err}"
                ) from err
        else:
            raise docker_exceptions.ContainerDoesNotExist(
                f"cannot stop the not exist container"
            )

    def __exec(self, command: str) -> ExecResult:
        try:
            if self.__docker_container is None:
                raise docker_exceptions.ExecOnContainerError(
                    f"the container {self.__name} doesn't exist"
                )

            self.__docker_container.reload()

            if self.__docker_container.status != "running":
                raise docker_exceptions.ExecOnContainerError(
                    f"the node {self.__name} is stopped"
                )

            start = time.perf_counter_ns()
            result = self.__docker_container.exec_run(command, demux=True)
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
                f"cannot execute the command {command} on the container {self.__docker_container.name}"  # type: ignore
            ) from err

    def __update(self, new_config: NodeConfig) -> None:
        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            self.__config = new_config
        else:
            try:
                self.__docker_container.update(  # type: ignore
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
        if self.__docker_container is None:
            return None

        self.__docker_container.reload()
        return self.__docker_container.id

    def docker_commit(self, pause: bool = True) -> tuple[docker_images.Image, str]:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the node {self.__name} is not deployed"
            )

        if self.__docker_container is None:
            raise docker_exceptions.ContainerDoesNotExist(
                f"the node {self.__name} does not have its container to commit"
            )

        try:
            snapshot_repo = f"snapshot_{str(self.__uuid)}"
            snapshot_tag = "v0"
            return (
                self.__docker_container.commit(  # type: ignore
                    repository=snapshot_repo, tag=snapshot_tag, pause=pause
                ),
                f"{snapshot_repo}:{snapshot_tag}",
            )
        except docker.errors.APIError as err:
            raise docker_exceptions.FailedToCommit(
                f"failed to commit the container {self.__name}"
            ) from err

    # ------ приватные проверки

    def __is_state_as_required(self, required: EntityState) -> bool:
        return self.__state is required
