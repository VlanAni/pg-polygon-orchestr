import docker
import docker.errors
import docker.models.images as docker_images
import docker.models.containers as docker_containers
import time

from ..configs.node_config import NodeConfig
from ..interfaces.exec_result import ExecResult
from .docker_deployer import DockerDeployer
from ..exception import docker_exceptions, common_exceptions
from ..interfaces import entity_state, types, mount_config
from pg_polygon_orchestr.core.interfaces.types import Type
from ..interfaces.node import Node


class DockerNode(Node):
    def __init__(self, name: str, config: NodeConfig, deployer: DockerDeployer) -> None:
        self.__name = name
        self.__config = config
        self.__deployer = deployer
        self.__image_name: str = ""
        self.__state: entity_state.EntityState = entity_state.EntityState.NOT_DEPLOYED
        self.__docker_image: docker_images.Image | None = None
        self.__docker_container: docker_containers.Container | None = None

    # ----- Интерфейсные методы

    def deploy(self) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__name} is removed"
            )

        if self.__is_state_as_required(required=entity_state.EntityState.DEPLOYED):
            raise common_exceptions.EntityIsAlreadyDeployed(
                f"the node {self.__name} is already deployed"
            )

        self.__deploy()

    def clear(self) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__name} is removed"
            )

        if self.__is_state_as_required(required=entity_state.EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the node {self.__name} is not deployed"
            )

        self.__clear()

    def start(self, mount_configs: list[mount_config.MountConfig] = []) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__name} is removed"
            )

        if self.__is_state_as_required(required=entity_state.EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the node {self.__name} is not deployed"
            )

        self.__start(mount_configs=mount_configs)

    def stop(self, timeout: int) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__name} is removed"
            )

        if self.__is_state_as_required(required=entity_state.EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the node {self.__name} is not deployed"
            )

        self.__stop(timeout=timeout)

    def exec(self, command: str) -> ExecResult:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__name} is removed"
            )

        if self.__is_state_as_required(required=entity_state.EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the node {self.__name} is not deployed"
            )

        return self.__exec(command=command)

    def update(self, new_config: NodeConfig) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__name} is removed"
            )

        self.__update(new_config=new_config)

    def remove(self) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the node {self.__name} is removed"
            )

        self.__remove()

    def get_type(self) -> Type:
        return types.Type.DOCKER

    def get_name(self) -> str:
        return self.__name

    # ------ приватные коллбеки

    def __deploy(self) -> None:
        image_tag = f"image_node_{self.__name}:v0"
        self.__image_name = image_tag
        try:
            image = self.__deployer.build_image(  # type: ignore
                who_ask=self, config=self.__my_config, image_tag=image_tag
            )

            if image is None:
                raise docker_exceptions.DockerDeployError(
                    f"the node {self.__name} is not registred"
                )

            self.__docker_image = image
            self.__state = entity_state.EntityState.DEPLOYED
        except docker_exceptions.ImageBuildError as err:
            raise docker_exceptions.DockerDeployError(
                f"failed to build a docker image: {err}"
            ) from err

    def __clear(self) -> None:
        try:
            self.__docker_container.remove()  # type: ignore
            self.__deployer.delete_image(who_ask=self, image=self.__image_name)  # type: ignore
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
        self.__state = entity_state.EntityState.NOT_DEPLOYED

    def __remove(self) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.DEPLOYED):
            try:
                self.__docker_container.remove(force=True)  # type: ignore
                self.__deployer.delete_image(who_ask=self, image=self.__image_name, force=True)  # type: ignore
            except docker.errors.APIError as err:
                raise docker_exceptions.DockerClearError(
                    f"failed to force remove node's {self.__name} container"
                ) from err
            except docker_exceptions.FailedToDeleteAnImage as err:
                raise docker_exceptions.DockerClearError(
                    f"failed to force remove node's {self.__name} image {self.__image_name}"
                ) from err

        self.__deployer.remove_node(who_ask=self)  # type: ignore

        self.__docker_container = None
        self.__image_name = ""
        self.__docker_image = None
        self.__config = None
        self.__deployer = None
        self.__state = entity_state.EntityState.REMOVED

    def __start(self, mount_configs: list[mount_config.MountConfig] = []) -> None:
        if self.__docker_container is None:
            try:
                container = self.__deployer.create_container(  # type: ignore
                    who_ask=self,
                    image=self.__docker_image,  # type: ignore
                    config=self.__config,  # type: ignore
                    name=self.__name,
                    mount_configs=mount_configs,
                )

                if container is None:
                    raise docker_exceptions.DockerContStartError(
                        f"the node {self.__name} is not registred"
                    )

                self.__docker_container = container
            except docker_exceptions.ResourceCreationError as err:
                raise docker_exceptions.DockerContStartError(
                    f"failed to create a docker container for the node {self.__name}"
                ) from err

        else:
            try:
                self.__docker_container.reload()

                if self.__docker_container.status == "running":
                    raise docker_exceptions.DockerContStartError(
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
                    raise docker_exceptions.DockerContStopError(
                        f"the node {self.__name} is already stopped"
                    )

                self.__docker_container.stop(timeout=timeout)
            except docker.errors.APIError as err:
                raise docker_exceptions.DockerContStopError(
                    f"cannot stop the container {self.__docker_container.name}: {err}"
                ) from err
        else:
            raise docker_exceptions.DockerContStopError(
                f"cannot stop the not exist container"
            )

    def __exec(self, command: str) -> ExecResult:
        try:
            self.__docker_container.reload()  # type: ignore

            if self.__docker_container.status != "running":  # type: ignore
                raise docker_exceptions.ExecOnContainerError(
                    f"the node {self.__name} is stopped"
                )

            start = time.perf_counter_ns()
            result = self.__docker_container.exec_run(command, demux=True)  # type: ignore
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
        if self.__is_state_as_required(required=entity_state.EntityState.NOT_DEPLOYED):
            self.__config = new_config
        else:
            try:
                self.__docker_container.update(  # type: ignore
                    mem_limit=self.__config.mem_limit,  # type: ignore
                    cpu_period=100000,
                    cpu_quota=self.__config.cpu_limit * 100000,  # type: ignore
                )

                self.__my_config = new_config

            except docker.errors.APIError as err:
                raise docker_exceptions.UpdateContainerConfError(
                    f"server returns an error: {err}"
                ) from err

    # ------ докер-специфичные функции

    def share_container_id(self) -> str | None:
        if self.__docker_container is None:
            return None

        self.__docker_container.reload()
        return self.__docker_container.id

    # ------ приватные проверки

    def __is_state_as_required(self, required: entity_state.EntityState) -> bool:
        return self.__state == required
