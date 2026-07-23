from ..configs.node_config import NodeConfig
from .deployer import Deployer
from ..nodes.docker_node import DockerNode
from ..nodes.node import Node

import docker
import docker.errors
import logging
from pathlib import Path

import sys

from ..logger_config.info_filter import INFO_Filter

from ..exception import docker_exceptions


class DockerDeployer(Deployer):

    def __configure_logger(self) -> None:
        self.logger = logging.getLogger("docker_deployer")

        self.logger.setLevel(logging.INFO)

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
        self.__docker_nodes: list[DockerNode] = []
        self.__images_ids: set[str] = set()
        self.__nodes_id_counter = 0
        self.__docker_session = None
        self.__configure_logger()

    def deploy(self, config: NodeConfig) -> Node:
        if self.__docker_session is None:
            self.logger.info("open a new connection to the docker server")
            try:
                self.__docker_session = docker.from_env()
            except docker.errors.DockerException:
                raise docker_exceptions.DockerConnectionError

            self.logger.info("new connection opened successfully")

        self.logger.info("deploying new docker-node...")

        node_id = self.__nodes_id_counter
        image_name = f"docker_node_{node_id}_image"

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
            id=node_id,
        )

        self.logger.info("new docker-node created")

        self.__docker_nodes.append(docker_node)

        self.__nodes_id_counter += 1

        return docker_node

    # these method allows you to remove all containers, all images and close the connection
    def destroy_everything(self) -> None:

        if self.__docker_session is None:
            self.logger.info("there is no any connections to the docker")
            return

        for node in self.__docker_nodes:
            node.stop(5)
            node.clearContainer()

        for image_id in self.__images_ids:
            try:
                self.__docker_session.images.remove(image_id, force=True)  # type: ignore
            except docker.errors.NotFound:
                self.logger.warning(f"docker image with id {image_id} not found")
            except docker.errors.APIError:
                self.logger.error("docker server returns an error!")

        self.__docker_session.close()
        self.__docker_session = None

        self.__docker_nodes.clear()
        self.__images_ids.clear()

    def getNodes(self) -> list[DockerNode]:
        return self.__docker_nodes.copy()

    def getImages(self) -> set[str]:
        return self.__images_ids.copy()
