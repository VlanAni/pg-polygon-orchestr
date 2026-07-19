from ..configs.config import Config
from .deployer import Deployer
from ..nodes.docker_node import DockerNode
from ..nodes.node import Node

import docker
import docker.errors
import logging
from pathlib import Path

from ..exception import docker_exceptions


class DockerDeployer(Deployer):

    def __init__(self) -> None:
        self.docker_nodes_map: dict[int, DockerNode] = {}
        self.nodes_id_counter = 0
        self.docker_session = None
        self.logger = logging.getLogger("docker_deployer")

    def deploy(self, config: Config) -> Node:
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
            self.logger.info(f"cannot build an image {image_name} from the Dockerfile")

            raise docker_exceptions.ImageBuildError

        except docker.errors.APIError:
            self.logger.info("server returns an error")

            raise docker_exceptions.DeploymentError

        except docker.errors.DockerException:
            self.logger.info("unpredictable error")

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
                self.logger.info("docker container not found")
            except docker.errors.APIError:
                self.logger.info("docker server returns an error!")

            try:
                # we must delete all images
                self.docker_session.images.remove(image.id, force=True)
            except docker.errors.NotFound:
                self.logger.info("docker image not found")
            except docker.errors.APIError:
                self.logger.info("docker server returns an error!")

        self.docker_session.close()
