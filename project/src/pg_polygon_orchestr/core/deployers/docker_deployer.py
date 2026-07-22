from ..configs.node_config import NodeConfig
from .deployer import Deployer
from ..nodes.docker_node import DockerNode
from ..nodes.node import Node

import docker
import docker.errors
import logging
from pathlib import Path

import sys

from ..exception import docker_exceptions


class DockerDeployer(Deployer):

    def __configure_logger(self) -> None:
        self.logger = logging.getLogger("docker_deployer")

        self.logger.setLevel(logging.INFO)

        info_handler = logging.StreamHandler(stream=sys.stdout)
        info_handler.setLevel(logging.INFO)

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
        self.docker_nodes_map: dict[int, DockerNode] = {}
        self.nodes_id_counter = 0
        self.docker_session = None
        self.__configure_logger()

    def deploy(self, config: NodeConfig) -> Node:
        if self.docker_session is None:
            self.logger.info("open a new connection to the docker server")
            try:
                self.docker_session = docker.from_env()
            except docker.errors.DockerException:
                raise docker_exceptions.DockerConnectionError

            self.logger.info("new connection opened successfully")

        self.logger.info("deploying new docker-node...")

        node_id = self.nodes_id_counter
        image_name = f"docker_node_{node_id}_image"

        # getting path for the build-in dockerfile (use __file__ dunder variable)
        try:
            image = self.docker_session.images.build(
                path=str(Path(__file__).parent),
                buildargs={"OS_IMAGE": config.os_name},
                tag=image_name,
            )[0]
        except docker.errors.BuildError:
            self.logger.error(f"cannot build an image {image_name} from the Dockerfile")

            raise docker_exceptions.ImageBuildError

        except docker.errors.APIError:
            self.logger.error("server returns an error")

            raise docker_exceptions.DeploymentError

        except docker.errors.DockerException:
            self.logger.error("unpredictable error")

            raise docker_exceptions.DeploymentError

        docker_node = DockerNode(
            docker_client=self.docker_session,
            image=image,
            config=config,
            id=node_id,
        )

        self.logger.info("new docker-node created")

        self.docker_nodes_map[node_id] = docker_node
        self.nodes_id_counter += 1

        return docker_node

    # these method allows you to remove all containers, all images and close the connection
    def destroy_everything(self) -> None:

        if self.docker_session is None:
            self.logger.info("there is no any connections to the docker")
            return

        for node_id in self.docker_nodes_map.keys():
            node = self.docker_nodes_map.get(node_id)

            container_name = f"docker_node_{node_id}_container"
            if node.my_container is not None:
                container_name = node.my_container.name

            image = node.my_image

            try:
                # we must stop all containers
                container_desc = self.docker_session.containers.get(container_name)
                container_desc.remove(force=True, v=True)
            except docker.errors.NotFound:
                self.logger.warning("docker container not found")
            except docker.errors.APIError:
                self.logger.error("docker server returns an error!")

            try:
                # we must delete all images
                self.docker_session.images.remove(image.id, force=True)
            except docker.errors.NotFound:
                self.logger.warning("docker image not found")
            except docker.errors.APIError:
                self.logger.error("docker server returns an error!")

        self.docker_session.close()
