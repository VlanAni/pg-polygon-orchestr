import docker
import docker.errors
import docker.models.networks as dockerapi_networks
import docker.models.images as dockerapi_images
import docker.models.containers as dockerapi_containers
import docker.models.volumes as dockerapi_volumes
from pathlib import Path

from ..exception import docker_exceptions
from ..exception import common_exceptions
from ..configs import node_config, volume_config, net_config
from ..interfaces import deployer, mount_config, node

from . import docker_node, docker_volume, docker_network


class DockerDeployer(deployer.Deployer):
    def __init__(self) -> None:
        self.__docker_nodes: dict[str, docker_node.DockerNode] = dict()
        self.__docker_networks: dict[str, docker_network.DockerNetwork] = dict()
        self.__docker_volumes: dict[str, docker_volume.DockerVolume] = dict()
        self.__docker_session = None
        self.__default_bridge: dockerapi_networks.Network | None = None

    # ----- ИНТЕРФЕЙСНЫЕ МЕТОДЫ

    # ------ докер-специфичные функции

    def build_image(
        self,
        who_ask: docker_node.DockerNode,
        config: node_config.NodeConfig,
        image_tag: str,
    ) -> dockerapi_images.Image | None:
        node_name = who_ask.get_name()

        search_result = self.__docker_nodes.get(node_name, None)

        if search_result is None or (not (search_result is who_ask)):
            return None

        if self.__docker_session is None:
            self.__docker_session = docker.from_env()

        try:
            image = self.__docker_session.images.build(
                path=str(Path(__file__).parent),
                buildargs={"OS_IMAGE": config.os},
                tag=image_tag,
            )[0]

            return image
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

    def create_container(
        self,
        who_ask: docker_node.DockerNode,
        image: dockerapi_images.Image,
        config: node_config.NodeConfig,
        name: str,
        mount_configs: list[mount_config.MountConfig],
    ) -> dockerapi_containers.Container | None:
        node_name = who_ask.get_name()

        search_result = self.__docker_nodes.get(node_name, None)

        if search_result is None or (not (search_result is who_ask)):
            return None

        if self.__docker_session is None:
            self.__docker_session = docker.from_env()

        try:
            container = self.__docker_session.containers.run(
                image=image,
                cpu_period=config.cpu_limit,
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
                    networks = self.__docker_session.networks.list(names=["bridge"])  # type: ignore
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

    def delete_image(
        self, who_ask: docker_node.DockerNode, image: str, force: bool = False
    ) -> None:
        node_name = who_ask.get_name()

        search_result = self.__docker_nodes.get(node_name, None)

        if search_result is None or (not (search_result is who_ask)):
            return None

        if self.__docker_session is None:
            self.__docker_session = docker.from_env()

        try:
            self.__docker_session.images.remove(image=image, force=force)  # type: ignore
        except Exception as err:
            raise docker_exceptions.FailedToDeleteAnImage(
                f"cannot delete the image {image}"
            ) from err

    def remove_node(self, who_ask: docker_node.DockerNode) -> None:
        node_name = who_ask.get_name()

        search_result = self.__docker_nodes.get(node_name, None)

        if search_result is not None and search_result is who_ask:
            self.__docker_nodes.pop(node_name)

    def create_volume(
        self,
        who_ask: docker_volume.DockerVolume,
        volume_config: volume_config.VolumeConfig,
    ) -> dockerapi_volumes.Volume | None:
        volume_name = who_ask.get_name()

        search_result = self.__docker_volumes.get(volume_name, None)

        if search_result is None or (not (search_result is who_ask)):
            return None

        if self.__docker_session is None:
            self.__docker_session = docker.from_env()

        try:
            config = volume_config
            volume = self.__docker_session.volumes.create(name=volume_name, driver=config.docker_volume_driver, driver_opts=config.docker_driver_options)  # type: ignore
            return volume
        except docker.errors.APIError as err:
            raise docker_exceptions.ResourceCreationError(
                f"failed to create the volume {volume_name}"
            ) from err

    def remove_volume(self, who_ask: docker_volume.DockerVolume) -> None:
        volume_name = who_ask.get_name()

        search_result = self.__docker_volumes.get(volume_name, None)

        if search_result is not None and search_result is who_ask:
            self.__docker_volumes.pop(volume_name)

    def create_network(
        self, who_ask: docker_network.DockerNetwork, config: net_config.NetConfig
    ) -> dockerapi_networks.Network | None:
        network_name = who_ask.get_name()

        search_result = self.__docker_networks.get(network_name, None)

        if search_result is None or not (search_result is who_ask):
            return None

        if self.__docker_session is None:
            self.__docker_session = docker.from_env()

        try:
            network = self.__docker_session.networks.create(
                name=network_name,
                enable_ipv6=config.ipv6,
                driver=config.docker_net_driver,
                internal=config.internal,
            )

            return network
        except docker.errors.APIError as err:
            raise docker_exceptions.ResourceCreationError(
                f"cannot create the network {network_name}"
            ) from err

    def remove_network(self, who_ask: docker_network.DockerNetwork) -> None:
        network_name = who_ask.get_name()

        search_result = self.__docker_networks.get(network_name, None)

        if search_result is not None and search_result is who_ask:
            self.__docker_networks.pop(network_name)

    def check_node_is_known(
        self, who_ask: docker_network.DockerNetwork, node: docker_node.DockerNode
    ) -> bool | None:
        net_name = who_ask.get_name()

        search_result = self.__docker_networks.get(net_name, None)

        if search_result is None or not (search_result is who_ask):
            return None

        node_search_result = self.__docker_nodes.get(node.get_name(), None)

        return node_search_result is not None and node_search_result is node

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
