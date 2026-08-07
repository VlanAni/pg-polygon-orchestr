from ..interfaces import Volume
from ..configs.volume_config import VolumeConfig
from ..exception import docker_exceptions, common_exceptions
from . import docker_session

import docker.errors as dockerapi_errors

from ..meta import EntityState, Type


class DockerVolume(Volume):
    def __init__(
        self,
        name: str,
        config: VolumeConfig,
        session: docker_session.DockerClientSession,
    ) -> None:
        self.__name = name
        self.__config = config
        self.__state = EntityState.NOT_DEPLOYED
        self.__shared_docker_session = session
        self.__volume = None

    # ------ интерфейсные методы

    def get_name(self) -> str:
        return self.__name

    def get_type(self) -> Type:
        return Type.DOCKER

    def deploy(self) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the volume {self.__name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.DEPLOYED):
            raise common_exceptions.EntityIsAlreadyDeployed(
                f"the volume {self.__name} is deployed"
            )

        self.__deploy()

    def clear(self) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the volume {self.__name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the volume {self.__name} is not deployed"
            )

        self.__clear()

    def remove(self) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the volume {self.__name} is removed"
            )

        self.__remove()

    # ------ приватные коллбеки

    def __deploy(self) -> None:
        try:
            volume = self.__shared_docker_session.ask_to_create_volume(  # type: ignore
                volume_name=self.__name, volume_config=self.__config  # type: ignore
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
        self.__state = EntityState.DEPLOYED

    def __clear(self) -> None:
        try:
            self.__volume.remove()  # type: ignore
        except dockerapi_errors.APIError as err:
            raise docker_exceptions.DockerClearError(
                f"failed to remove a docker volume {self.__name}. Maybe in used"
            ) from err

        self.__state = EntityState.NOT_DEPLOYED
        self.__volume = None

    def __remove(self) -> None:
        if self.__is_state_as_required(required=EntityState.DEPLOYED):
            try:
                self.__volume.remove(force=True)  # type: ignore
            except dockerapi_errors.APIError as err:
                raise docker_exceptions.DockerRemoveError(
                    f"failed to force remove a docker volume {self.__name}"
                ) from err

        self.__state = EntityState.REMOVED
        self.__volume = None
        self.__config = None

    # ------ приватные методы

    def __is_state_as_required(self, required: EntityState) -> bool:
        return self.__state == required
