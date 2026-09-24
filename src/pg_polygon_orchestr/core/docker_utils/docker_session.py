import docker
import docker.models.containers as dockerapi_containers
import docker.models.images as dockerapi_images
import docker.models.networks as dockerapi_networks
import docker.models.volumes as dockerapi_volumes
import docker.errors
import docker.types as dockerapi_types

from pathlib import Path

from ..infra_configs import NodeConfig, NetConfig
from ..common_types import SubnetConfig
from ..exception import docker_exceptions


class DockerClientSession:
    def __init__(self) -> None:
        self.__session: docker.client.DockerClient | None = None
        self.__default_bridge: dockerapi_networks.Network | None = None

    # ------ публичные методы

    def ask_to_build_image(
        self,
        config: NodeConfig,
        image_tag: str,
    ) -> dockerapi_images.Image:
        if self.__session is None:
            try:
                self.__open_docker_session()
            except Exception as err:
                raise docker_exceptions.ResourceCreationError(
                    f"failed to open docker session"
                )

        try:

            if self.__session is None:
                raise docker_exceptions.ResourceCreationError(
                    f"there are no a Docker Client Session"
                )

            image = self.__session.images.build(
                path=str(Path(__file__).parent),
                buildargs={"OS_IMAGE": config.os},
                tag=image_tag,
                rm=True,
                forcerm=True,
            )[0]

        except docker.errors.BuildError as err:

            raise docker_exceptions.ResourceCreationError(
                f"cannot build an image {image_tag} from the Dockerfile"
            ) from err

        except docker.errors.APIError as err:

            raise docker_exceptions.ResourceCreationError(
                f"server returns an error: {err}"
            ) from err

        except docker.errors.DockerException as err:

            raise docker_exceptions.ResourceCreationError(
                f"unpredictable error: {err}"
            ) from err

        return image

    def ask_to_create_a_container(
        self,
        image: dockerapi_images.Image,
        name: str,
        config: NodeConfig,
        mounts: list[dockerapi_types.Mount],
    ) -> dockerapi_containers.Container:
        if self.__session is None:
            try:
                self.__open_docker_session()
            except Exception as err:
                raise docker_exceptions.ResourceCreationError(
                    f"failed to open a Docker Client Session"
                )

        try:

            if self.__session is None:
                raise docker_exceptions.ResourceCreationError(
                    f"failed to fetch a Docker Client Session"
                )

            container = self.__session.containers.create(
                image=image,
                cpu_period=100000,
                cpu_quota=100000 * config.cpu_limit,
                mem_limit=config.mem_limit,
                detach=True,
                name=name,
                mounts=mounts,
                **config.docker_params.to_host_config_kwargs(),
            )

        except docker.errors.ImageNotFound as err:

            raise docker_exceptions.ResourceCreationError(
                f"the image {image} not found"
            ) from err

        except docker.errors.APIError as err:

            raise docker_exceptions.ResourceCreationError(
                f"server returns an error"
            ) from err

        if config.docker_params.detach_from_default_bridge:
            try:

                container.start()

            except docker.errors.APIError as err:

                container.remove(force=True)

                raise docker_exceptions.ResourceCreationError(
                    f"failed to start container to disconnect from default bridge"
                ) from err

            if self.__default_bridge is None:
                try:

                    networks = self.__session.networks.list(names=["bridge"])  # type: ignore # тип опции `names` - list[str]

                except docker.errors.APIError as err:

                    container.remove(force=True)
                    raise docker_exceptions.ResourceCreationError(
                        f"cannot get the default bridge"
                    ) from err

                if len(networks) == 0:
                    container.remove(force=True)
                    raise docker_exceptions.ResourceCreationError(
                        f"cannot get the default bridge"
                    )

                self.__default_bridge = networks[0]

            try:

                self.__default_bridge.disconnect(container=container)

            except docker.errors.APIError as err:

                container.remove(force=True)
                raise docker_exceptions.ResourceCreationError(
                    f"failed to disconnect container from the default bridge"
                ) from err

            try:

                container.stop(timeout=0)

            except docker.errors.APIError as err:

                container.remove(force=True)

                raise docker_exceptions.ResourceCreationError(
                    f"failed to disconnect container from the default bridge"
                ) from err

        return container

    def ask_to_delete_image(self, image: str, force: bool = False) -> None:
        if self.__session is None:
            self.__open_docker_session()

        try:
            self.__session.images.remove(image=image, force=force)  # type: ignore
        except Exception as err:
            raise docker_exceptions.FailedToDeleteAnImage(
                f"cannot delete the image {image}"
            ) from err

    def ask_to_create_volume(
        self,
        volume_name: str,
    ) -> dockerapi_volumes.Volume | None:
        if self.__session is None:
            try:
                self.__open_docker_session()
            except Exception as err:
                raise docker_exceptions.ResourceCreationError(
                    f"failed to open a Docker Client Session"
                )

        try:

            if self.__session is None:
                raise docker_exceptions.ResourceCreationError(
                    f"the Docker Client Session is None"
                )

            volume = self.__session.volumes.create(name=volume_name)

            return volume

        except docker.errors.APIError as err:
            raise docker_exceptions.ResourceCreationError(
                f"failed to create the volume {volume_name}"
            ) from err

    def ask_to_create_network(
        self,
        name: str,
        config: NetConfig,
        subnet_configs: list[SubnetConfig],
    ) -> dockerapi_networks.Network:
        if self.__session is None:
            try:
                self.__open_docker_session()
            except Exception as err:
                raise docker_exceptions.ResourceCreationError(
                    f"failed to open a Docker Client Session"
                )

        ipam_config = self.__make_docker_ipam_config(subnet_configs=subnet_configs)

        try:

            if self.__session is None:
                raise docker_exceptions.ResourceCreationError(
                    f"the Docker Client Session is None"
                )

            network = self.__session.networks.create(
                name=name,
                driver=config.docker_net_options.driver,
                internal=config.docker_net_options.internal,
                ipam=ipam_config,
            )

        except docker.errors.APIError as err:

            raise docker_exceptions.ResourceCreationError(
                f"cannot create the network {name}"
            ) from err

        return network

    def close(self) -> None:
        if self.__session is not None:
            self.__session.close()

        self.__session = None

    # ------ приватные методы

    def __open_docker_session(self):
        try:
            self.__session = docker.from_env()
        except:
            raise Exception(f"failed to open client session")

        try:
            if not self.__session.ping():  # type: ignore
                self.__session = None
                raise Exception(f"Docker Daemon hasn't sent response")
        except docker.errors.APIError as err:
            self.__session = None
            raise Exception(f"failed to check connection") from err

    def __make_docker_ipam_config(
        self, subnet_configs: list[SubnetConfig]
    ) -> dockerapi_types.IPAMConfig:
        return dockerapi_types.IPAMConfig(
            pool_configs=[
                dockerapi_types.IPAMPool(
                    subnet=sc.subnet.with_prefixlen, gateway=str(sc.gateway)
                )
                for sc in subnet_configs
            ]
        )
