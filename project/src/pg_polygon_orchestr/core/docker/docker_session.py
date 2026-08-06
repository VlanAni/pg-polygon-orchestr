import docker
import docker.models.containers as dockerapi_containers
import docker.models.images as dockerapi_images
import docker.models.networks as dockerapi_networks
import docker.models.volumes as dockerapi_volumes
import docker.errors
from pathlib import Path

from ..configs import node_config, net_config, volume_config
from ..interfaces import mount_config
from ..exception import docker_exceptions


class DockerClientSession:
    def __init__(self) -> None:
        self.__session: docker.client.DockerClient | None = None
        self.__default_bridge: dockerapi_networks.Network | None = None

    # ------ публичные методы

    def ask_to_build_image(
        self,
        config: node_config.NodeConfig,
        image_tag: str,
    ) -> dockerapi_images.Image:
        if self.__session is None:
            self.__session = docker.from_env()

        try:
            image = self.__session.images.build(
                path=str(Path(__file__).parent),
                buildargs={"OS_IMAGE": config.os},
                tag=image_tag,
            )[0]
        except docker.errors.BuildError as err:
            raise docker_exceptions.ImageBuildError(
                f"cannot build an image {image_tag} from the Dockerfile"
            ) from err

        except docker.errors.APIError as err:
            raise docker_exceptions.ImageBuildError(
                f"server returns an error: {err}"
            ) from err

        except docker.errors.DockerException as err:
            raise docker_exceptions.ImageBuildError(
                f"unpredictable error: {err}"
            ) from err

        return image

    def ask_to_create_a_container(
        self,
        image: dockerapi_images.Image,
        name: str,
        config: node_config.NodeConfig,
        mount_configs: list[mount_config.MountConfig],
    ) -> dockerapi_containers.Container:
        if self.__session is None:
            self.__session = docker.from_env()

        try:
            container = self.__session.containers.run(
                image=image,
                cpu_period=100000,
                cpu_quota=100000 * config.cpu_limit,
                mem_limit=config.mem_limit,
                detach=True,
                name=name,
                cap_add=(["NET_ADMIN"] if config.net_settings_roots else None),
                sysctls=(
                    {"net.ipv4.ip_forward": "1"} if config.ip_forwarding else None
                ),
                volumes=self.__create_volume_mount_map(mount_configs=mount_configs),
            )
        except docker.errors.ImageNotFound as err:
            raise docker_exceptions.ResourceCreationError(
                f"the image {image} not found"
            ) from err

        except docker.errors.APIError as err:
            raise docker_exceptions.ResourceCreationError(
                f"server returns an error"
            ) from err

        if not (config.connect_to_docker_default):
            if self.__default_bridge is None:
                try:
                    networks = self.__session.networks.list(names=["bridge"])  # type: ignore
                except docker.errors.APIError as err:
                    container.remove(force=True)
                    raise docker_exceptions.ResourceCreationError(
                        f"cannot get the default bridge"
                    )

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
                )

        return container

    def ask_to_delete_image(self, image: str, force: bool = False) -> None:
        if self.__session is None:
            self.__session = docker.from_env()

        try:
            self.__session.images.remove(image=image, force=force)  # type: ignore
        except Exception as err:
            raise docker_exceptions.FailedToDeleteAnImage(
                f"cannot delete the image {image}"
            ) from err

    def ask_to_create_volume(
        self,
        volume_name: str,
        volume_config: volume_config.VolumeConfig,
    ) -> dockerapi_volumes.Volume | None:
        if self.__session is None:
            self.__session = docker.from_env()

        try:
            config = volume_config
            volume = self.__session.volumes.create(name=volume_name, driver=config.docker_volume_driver, driver_opts=config.docker_driver_options)  # type: ignore
            return volume
        except docker.errors.APIError as err:
            raise docker_exceptions.ResourceCreationError(
                f"failed to create the volume {volume_name}"
            ) from err

    def ask_to_create_network(
        self, name: str, config: net_config.NetConfig
    ) -> dockerapi_networks.Network | None:
        if self.__session is None:
            self.__session = docker.from_env()

        try:
            network = self.__session.networks.create(
                name=name,
                enable_ipv6=config.ipv6,
                driver=config.docker_net_driver,
                internal=config.internal,
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

    def __create_volume_mount_map(
        self, mount_configs: list[mount_config.MountConfig]
    ) -> dict[str, dict[str, str]]:
        mount_map: dict[str, dict[str, str]] = dict()

        for mount_config in mount_configs:
            name = mount_config.volume.get_name()
            mount_path = mount_config.mount_path
            ro = mount_config.read_only

            mount_map[name] = {"bind": mount_path, "mode": "ro" if ro else "rw"}

        return mount_map
