import docker
import docker.models.containers as dockerapi_containers
import docker.models.images as dockerapi_images
import docker.models.networks as dockerapi_networks
import docker.models.volumes as dockerapi_volumes
import docker.errors
import docker.types as dockerapi_types
from pathlib import Path

from ..configs import NodeConfig, NetConfig, VolumeConfig
from ..meta import MountConfig, MountableType, SubnetConfig
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
            self.__session = docker.from_env()

        try:
            image = self.__session.images.build(
                path=str(Path(__file__).parent),
                buildargs={"OS_IMAGE": config.os},
                tag=image_tag,
                rm=True,
                forcerm=True,
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
        config: NodeConfig,
        mount_configs: list[MountConfig],
    ) -> dockerapi_containers.Container:
        if self.__session is None:
            self.__session = docker.from_env()

        try:
            container = self.__session.containers.create(
                image=image,
                cpu_period=100000,
                cpu_quota=100000 * config.cpu_limit,
                mem_limit=config.mem_limit,
                detach=True,
                name=name,
                cap_add=config.docker_linux_cap_add,
                cap_drop=config.docker_linux_cap_drop,
                mounts=self.__make_mount_list(mount_configs=mount_configs),
                environment=config.docker_environment,
                sysctls=self.__make_sysctls_dict(config=config),
            )
        except docker.errors.ImageNotFound as err:
            raise docker_exceptions.ResourceCreationError(
                f"the image {image} not found"
            ) from err

        except docker.errors.APIError as err:
            raise docker_exceptions.ResourceCreationError(
                f"server returns an error"
            ) from err

        if not (config.docker_default_bridge_connection):
            try:
                container.start()
            except docker.errors.APIError as err:
                container.remove(force=True)
                raise docker_exceptions.ResourceCreationError(
                    f"failed to start container to disconnect from default bridge"
                ) from err

            if self.__default_bridge is None:
                try:
                    networks = self.__session.networks.list(names=["bridge"])  # type: ignore
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
        volume_config: VolumeConfig,
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
        self,
        name: str,
        config: NetConfig,
        subnet_configs: list[SubnetConfig],
    ) -> dockerapi_networks.Network:
        if self.__session is None:
            self.__session = docker.from_env()

        ipam_config = self.__make_docker_ipam_config(subnet_configs=subnet_configs)

        try:
            network = self.__session.networks.create(
                name=name,
                driver=config.docker_net_driver,
                internal=config.internal,
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

    def __make_mount_list(
        self, mount_configs: list[MountConfig]
    ) -> list[dockerapi_types.Mount]:
        mount_list: list[dockerapi_types.Mount] = list()

        for mntcfg in mount_configs:
            source = mntcfg.mounted.source()
            mount_path = mntcfg.mount_path
            ro = mntcfg.read_only

            if mntcfg.mounted.mtype() == MountableType.VOLUME:
                mount_list.append(
                    dockerapi_types.Mount(
                        target=mount_path, source=source, type="volume", read_only=ro
                    )
                )
            elif mntcfg.mounted.mtype() == MountableType.HOSTPATH:
                mount_list.append(
                    dockerapi_types.Mount(
                        target=mount_path, source=source, type="bind", read_only=ro
                    )
                )

        return mount_list

    def __make_sysctls_dict(self, config: NodeConfig) -> dict[str, str] | None:
        sysctl_dict: dict[str, str] = {}

        if config.docker_container_ip_forwarding:
            sysctl_dict["net.ipv4.ip_forward"] = "1"

        return sysctl_dict if sysctl_dict else None

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
