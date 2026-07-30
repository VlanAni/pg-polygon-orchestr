from ..configs.node_config import NodeConfig
from ..configs.infra_config import InfConfig
from .deployer import Deployer
from ..nodes.docker_infrastructure import DockerInfrastructure
from ..nodes.docker_node import DockerNode

import docker
import docker.errors
import docker.models.networks as docker_networks


import logging
from pathlib import Path

import sys
from ..logger_config.info_filter import INFO_Filter

from ..exception import docker_exceptions
from ..exception import common_exceptions


class DockerDeployer(Deployer):

    def __configure_logger(self) -> None:
        self.logger = logging.getLogger("docker_deployer")

        self.logger.setLevel(logging.INFO)

        if self.logger.handlers:
            return

        info_handler = logging.StreamHandler(stream=sys.stdout)
        info_handler.setLevel(logging.INFO)
        info_handler.addFilter(INFO_Filter())

        trouble_handler = logging.StreamHandler(stream=sys.stderr)
        trouble_handler.setLevel(logging.WARNING)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        info_handler.setFormatter(formatter)
        trouble_handler.setFormatter(formatter)

        self.logger.addHandler(info_handler)
        self.logger.addHandler(trouble_handler)

    def __init__(self) -> None:
        self.__docker_nodes: dict[str, DockerNode] = dict()  # реестр созданных нод
        self.__images_ids: set[str] = set()  # реестр айдишников образов
        self.__infrastructures: list[DockerInfrastructure] = (
            []
        )  # реестр развёрнутых инфраструктур
        self.__networks: dict[str, docker_networks.Network] = (
            dict()
        )  # реестр созданных сетей
        self.__docker_session = None  # состояние сессии
        self.__configure_logger()

    # деплоинг отдельной ноду
    def deploy_node(
        self, name: str, config: NodeConfig, nets: list[str] | None = None
    ) -> DockerNode:
        if self.__docker_nodes.get(name, None) is not None:

            raise common_exceptions.NodeWithThatNameAlreadyExistsException(
                f"the node with the name {name} already exists"
            )

        if self.__docker_session is None:
            self.logger.info("open a new connection to the docker server")
            try:
                self.__docker_session = docker.from_env()
            except docker.errors.DockerException as err:

                raise docker_exceptions.DockerConnectionError(
                    f"cannot connect to the docker daemon to deploy the node {name}: {err}"
                ) from err

            self.logger.info("new connection opened successfully")

        self.logger.info("deploying new docker-node...")

        networks: list[docker_networks.Network] = []

        for net_name in nets or []:
            net_obj = self.__networks.get(net_name, None)

            if net_obj is None:

                raise common_exceptions.ThereIsNoDataForThisKeyException(
                    f"cannot find the network with the name {net_name}"
                )

            networks.append(net_obj)

        image_name = f"{name}_image"

        # getting path for the build-in dockerfile (use __file__ dunder variable)
        try:
            image = self.__docker_session.images.build(
                path=str(Path(__file__).parent),
                buildargs={"OS_IMAGE": config.os_name},
                tag=image_name,
            )[0]
            self.logger.info(f"image {image} was built")
        except docker.errors.BuildError as err:
            self.logger.error(f"cannot build an image {image_name} from the Dockerfile")

            raise docker_exceptions.ImageBuildError(
                f"cannot build an image {image_name} from the Dockerfile"
            ) from err

        except docker.errors.APIError as err:
            self.logger.error(f"server returns an error: {err}")

            raise docker_exceptions.DeploymentError(
                f"server returns an error: {err}"
            ) from err

        except docker.errors.DockerException as err:
            self.logger.error(f"unpredictable error: {err}")

            raise docker_exceptions.DeploymentError(
                f"unpredictable error: {err}"
            ) from err

        self.__images_ids.add(image.id)  # type: ignore

        docker_node = DockerNode(
            docker_client=self.__docker_session,
            image=image,
            config=config,
            name=name,
            default_net=config.connect_to_docker_default_net,
            networks=networks,
        )

        self.logger.info("new docker-node created")

        self.__docker_nodes[name] = docker_node

        return docker_node

    # функция деплоинга инфраструктуры
    def deploy_infrastructure(self, inf_config: InfConfig) -> DockerInfrastructure:

        if self.__docker_session is None:
            self.logger.info("open a new connection to the docker server")
            try:
                self.__docker_session = docker.from_env()
            except docker.errors.DockerException as err:

                raise docker_exceptions.DockerConnectionError(
                    f"failed to open a docker client session: {err}"
                ) from err

        try:
            self.__create_networks(inf_config=inf_config)
        except docker_exceptions.CannotCreateDockerNetwork as err:

            raise docker_exceptions.CreateNetworkError(f"cannot create network: {err}")

        except common_exceptions.ThereIsNoDataForThisKeyException as err:

            raise common_exceptions.ThereIsNoDataForThisKeyException(
                f"cannot find data: {err}"
            ) from err

        nodes: list[DockerNode] = []

        for node_name in inf_config.get_node_names():

            config = inf_config.get_node_config(name=node_name)

            if config is None:

                raise common_exceptions.ThereIsNoDataForThisKeyException(
                    f"no config for the node {node_name}"
                )

            nets_names = inf_config.get_node_net_data(node_name=node_name)
            if nets_names is None:

                raise common_exceptions.ThereIsNoDataForThisKeyException(
                    f"cannot find networks names for this node: {node_name}"
                )

            try:
                node = self.deploy_node(name=node_name, config=config, nets=nets_names)
                nodes.append(node)
            except common_exceptions.NodeWithThatNameAlreadyExistsException as err:

                raise common_exceptions.CannotDeployNodeException(
                    f"Cannot deploy an infrasturcure with dublicates: {err}"
                ) from err

            except docker_exceptions.DockerConnectionError as err:

                raise common_exceptions.CannotDeployNodeException(
                    f"cannot connect to the docker daemon: {err}"
                ) from err

            except common_exceptions.ThereIsNoDataForThisKeyException as err:

                raise common_exceptions.CannotDeployNodeException(
                    f"cannot find needed data: {err}"
                ) from err

            except docker_exceptions.ImageBuildError as err:

                raise common_exceptions.CannotDeployNodeException(
                    f"cannot build an image: {err}"
                ) from err

            except docker_exceptions.DeploymentError as err:

                raise docker_exceptions.DeploymentError(
                    f"failed to deploy a node: {err}"
                ) from err

        inf = DockerInfrastructure(nodes=nodes, networks=list(self.__networks.values()))

        self.__infrastructures.append(inf)

        return inf

    # метод уничтожающий все контейнеры, сети и образы
    def destroy_everything(self) -> None:
        self.logger.info("DESTROYING")

        if self.__docker_session is None:
            self.logger.info("there is no any connections to the docker")
            return

        try:
            for node in self.__docker_nodes.values():
                try:
                    node.soft_destroy_container()
                except Exception as err:
                    err_message = f"some error during soft-destroying of the node: {node.get_name()}: {err}"

                    try:
                        node.force_destroy_container()
                    except Exception as err:

                        raise docker_exceptions.CannotDestroyTheNodeException(
                            f"cannot force destroy the node {node.get_name()} and {err_message}: {err}"
                        ) from err

            for image_id in self.__images_ids:
                try:
                    self.__docker_session.images.remove(image_id, force=True)  # type: ignore
                except docker.errors.NotFound as err:

                    # raise docker_exceptions.CannotDestroyTheImageException(
                    #     f"cannot find the image {image_id}: {err}"
                    # ) from err
                    pass

                except docker.errors.APIError as err:

                    raise docker_exceptions.CannotDestroyTheImageException(
                        f"cannot remove the image {image_id}: {err}"
                    ) from err

            for net_name in self.__networks.keys():
                net_obj = self.__networks[net_name]

                try:
                    net_obj.remove()
                except docker.errors.APIError as err:

                    raise docker_exceptions.CannotDestroyTheNetwork(
                        f"cannot remove the network {net_name}: {err}"
                    ) from err
        finally:
            self.__docker_session.close()
            self.__docker_session = None

            self.__docker_nodes.clear()
            self.__images_ids.clear()
            self.__networks.clear()

            for inf in self.__infrastructures:
                inf.mask_as_unusable()

        self.logger.info("DESTROYING DONE")

    # ГЕТТЕРЫ
    def get_nodes(self) -> dict[str, DockerNode]:
        return self.__docker_nodes.copy()

    def get_images(self) -> set[str]:
        return self.__images_ids.copy()

    def get_infrastructures(self) -> list[DockerInfrastructure]:
        return self.__infrastructures

    # функция создания сетей (возвращает айдишники сетей)
    def __create_networks(self, inf_config: InfConfig) -> None:

        if (
            self.__docker_session is None
        ):  # такая ситуация невозможна, потому что функция вызывается только после создания сети. Но проверка нужна для типобезопасности
            return

        for net_name in inf_config.get_net_names():
            net_config = inf_config.get_net_config(net_name)

            if net_config is None:
                raise common_exceptions.ThereIsNoDataForThisKeyException(
                    f"cannot find a config for this network: {net_name}"
                )

            try:
                net_obj = self.__docker_session.networks.create(
                    name=net_name,
                    driver=net_config.driver(),
                    internal=net_config.is_internal(),
                    enable_ipv6=net_config.ipv6_support(),
                )

                self.__networks[net_name] = net_obj
            except docker.errors.APIError as err:
                raise docker_exceptions.CannotCreateDockerNetwork(
                    f"cannot create docker network {net_name}: {err}"
                )
