from ..interfaces import volume, entity_state, types
from ..configs.volume_config import VolumeConfig
from ..exception import docker_exceptions, common_exceptions
from . import docker_deployer

import docker.errors as dockerapi_errors


class DockerVolume(volume.Volume):
    def __init__(
        self, name: str, config: VolumeConfig, deployer: docker_deployer.DockerDeployer
    ) -> None:
        self.__name = name
        self.__config = config
        self.__state = entity_state.EntityState.NOT_DEPLOYED
        self.__deployer = deployer
        self.__volume = None

    # ------ интерфейсные методы

    def get_name(self) -> str:
        return self.__name

    def get_type(self) -> types.Type:
        return types.Type.DOCKER

    def deploy(self) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the volume {self.__name} is removed"
            )

        if self.__is_state_as_required(required=entity_state.EntityState.DEPLOYED):
            raise common_exceptions.EntityIsAlreadyDeployed(
                f"the volume {self.__name} is deployed"
            )

        self.__deploy()

    def clear(self) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the volume {self.__name} is removed"
            )

        if self.__is_state_as_required(required=entity_state.EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the volume {self.__name} is not deployed"
            )

        self.__clear()

    def remove(self) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the volume {self.__name} is removed"
            )

        self.__remove()

    # ------ приватные коллбеки

    def __deploy(self) -> None:
        try:
            volume = self.__deployer.create_volume(  # type: ignore
                who_ask=self, volume_config=self.__config  # type: ignore
            )
        except docker_exceptions.ResourceCreationError as err:
            raise docker_exceptions.DockerDeployError(
                f"failed to deploy docker volume {self.__name}"
            ) from err

        if volume is None:
            raise docker_exceptions.DockerDeployError(
                f"failed to deploy docker volume {self.__name} because it is not registred"
            )

        self.__volume = volume
        self.__state = entity_state.EntityState.DEPLOYED

    def __clear(self) -> None:
        try:
            self.__volume.remove()  # type: ignore
        except dockerapi_errors.APIError as err:
            raise docker_exceptions.DockerClearError(
                f"failed to remove a docker volume {self.__name}. Maybe in used"
            ) from err

        self.__state = entity_state.EntityState.NOT_DEPLOYED
        self.__volume = None

    def __remove(self) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.DEPLOYED):
            try:
                self.__volume.remove(force=True)  # type: ignore
            except dockerapi_errors.APIError as err:
                raise docker_exceptions.DockerRemoveError(
                    f"failed to force remove a docker volume {self.__name}"
                ) from err

        self.__deployer.remove_volume(who_ask=self)  # type: ignore

        self.__state = entity_state.EntityState.REMOVED
        self.__volume = None
        self.__config = None
        self.__deployer = None

    # ------ приватные методы

    def __is_state_as_required(self, required: entity_state.EntityState) -> bool:
        return self.__state == required
