from ..configs.node_config import NodeConfig
from ..configs.infra_config import InfConfig
from .deployer import Deployer
from ..nodes.docker_infrastructure import DockerInfrastructure
from ..nodes.docker_node import DockerNode

import docker
import docker.errors
import logging
from pathlib import Path

import sys

from ..logger_config.info_filter import INFO_Filter

from ..exception import docker_exceptions, common_exceptions


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
        self.__docker_nodes: dict[str, DockerNode] = dict()
        self.__images_ids: set[str] = set()
        self.__infrastructures: list[DockerInfrastructure] = []
        self.__docker_session = None
        self.__configure_logger()

    def deploy_node(self, name: str, config: NodeConfig) -> DockerNode:
        if self.__docker_nodes.get(name, None) is not None:
            raise common_exceptions.NodeWithThatNameAlreadyExistsException(
                f"the node with the name {name} already exists"
            )

        if self.__docker_session is None:
            self.logger.info("open a new connection to the docker server")
            try:
                self.__docker_session = docker.from_env()
            except docker.errors.DockerException:
                raise docker_exceptions.DockerConnectionError
            self.logger.info("new connection opened successfully")

        self.logger.info("deploying new docker-node...")

        image_name = f"{name}_image"

        # getting path for the build-in dockerfile (use __file__ dunder variable)
        try:
            image = self.__docker_session.images.build(
                path=str(Path(__file__).parent),
                buildargs={"OS_IMAGE": config.os_name},
                tag=image_name,
            )[0]
            self.logger.info(f"image {image} was built")
        except docker.errors.BuildError:
            self.logger.error(f"cannot build an image {image_name} from the Dockerfile")
            raise docker_exceptions.ImageBuildError
        except docker.errors.APIError:
            self.logger.error("server returns an error")
            raise docker_exceptions.DeploymentError
        except docker.errors.DockerException:
            self.logger.error("unpredictable error")
            raise docker_exceptions.DeploymentError

        self.__images_ids.add(image.id)  # type: ignore

        docker_node = DockerNode(
            docker_client=self.__docker_session,
            image=image,
            config=config,
            name=name,
        )

        self.logger.info("new docker-node created")

        self.__docker_nodes[name] = docker_node

        return docker_node

    def deploy_infrastructure(self, inf_config: InfConfig) -> DockerInfrastructure:
        nodes: list[DockerNode] = []

        for node_name in inf_config.get_names():

            config = inf_config.get_config(name=node_name)

            if config is None:
                raise common_exceptions.ThereIsNodeConfigForNodeWithSuchNameException(
                    f"no config for the node {node_name}"
                )

            nodes.append(self.deploy_node(name=node_name, config=config))

        inf = DockerInfrastructure(nodes=nodes)

        self.__infrastructures.append(inf)

        return inf

    # these method allows you to remove all containers, all images and close the connection
    def destroy_everything(self) -> bool:
        self.logger.info("DESTROYING")

        if self.__docker_session is None:
            self.logger.info("there is no any connections to the docker")
            return True

        for node in self.__docker_nodes.values():
            if not (node.destroy_container()):
                self.logger.info(f"cannot delete container clearly")

                if not (node.force_destroy_container()):
                    self.logger.info(f"cannot force destroy container")
                    return False

        for image_id in self.__images_ids:
            try:
                self.__docker_session.images.remove(image_id, force=True)  # type: ignore
            except docker.errors.NotFound:
                self.logger.warning(f"docker image with id {image_id} not found")
            except docker.errors.APIError:
                self.logger.error("docker server returns an error!")
                return False

        self.__docker_session.close()
        self.__docker_session = None

        self.__docker_nodes.clear()
        self.__images_ids.clear()

        for inf in self.__infrastructures:
            inf.mask_as_unusable()

        self.logger.info("DESTROYING DONE")
        return True

    def get_nodes(self) -> dict[str, DockerNode]:
        return self.__docker_nodes.copy()

    def get_images(self) -> set[str]:
        return self.__images_ids.copy()

    def get_infrastructures(self) -> list[DockerInfrastructure]:
        return self.__infrastructures
