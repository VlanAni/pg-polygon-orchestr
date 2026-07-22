from .node import Node

import docker
import docker.errors
import docker.models.images

import sys

from ..configs.node_config import NodeConfig

import logging


class DockerNode(Node):
    def __configure_logger(self) -> None:
        self.my_logger = logging.getLogger(f"docker_node_{self.id}")

        self.my_logger.setLevel(logging.INFO)

        info_handler = logging.StreamHandler(stream=sys.stdout)
        info_handler.setLevel(logging.INFO)

        trouble_handler = logging.StreamHandler(stream=sys.stderr)
        trouble_handler.setLevel(logging.WARNING)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        info_handler.setFormatter(formatter)
        trouble_handler.setFormatter(formatter)

        self.my_logger.addHandler(info_handler)
        self.my_logger.addHandler(trouble_handler)

    def __init__(
        self,
        docker_client: docker.DockerClient,
        image: docker.models.images.Image,
        config: NodeConfig,
        id: int,
    ) -> None:
        self.my_session = docker_client
        self.my_image = image
        self.my_config = config
        self.my_container = None
        self.id = id
        self.__configure_logger()

    def start(self) -> None:
        if self.my_container is None:
            self.my_logger.info(
                f"starting a new container from the image {self.my_image}"
            )

            container_name = f"docker_node_{self.id}_container"

            try:
                self.my_container = self.my_session.containers.run(
                    self.my_image.tags[0],
                    nano_cpus=int(
                        self.my_config.cpu_limit * 1e9
                    ),  # do mult with cpu_limit and 1e-9 to get nanocpu-limit (it's universal)
                    mem_limit=self.my_config.ram_limit,  # hard limit for how many memory our container can use
                    detach=True,  # set detach as True to make .run non-block...
                    name=container_name,
                )
            except docker.errors.ContainerError:
                self.my_logger.error(
                    f"container {container_name} exited with non-zero code"
                )
                return
            except docker.errors.ImageNotFound:
                self.my_logger.warning(f"cannot find image {self.my_image}")
                self.my_container = None
                return
            except docker.errors.APIError:
                self.my_logger.error(f"server returns an error")
                self.my_container = None
                return

            self.my_logger.info(
                f"new container is running. Its' image - {self.my_image}"
            )
        else:
            self.my_logger.info(f"starting the container {self.my_container.name}")

            try:
                self.my_container.start()
            except docker.errors.APIError:
                self.my_logger.error(f"server returns an error")
                return

            self.my_logger.info(f"the container {self.my_container.name} is running")

    def stop(self) -> None:
        if self.my_container is not None:
            self.my_logger.info(f"stopping the container {self.my_container.name}")

            if self.my_container.status == "running":
                try:
                    self.my_container.stop()
                except docker.errors.APIError:
                    self.my_logger.error(f"server returns an error")
                    return

            self.my_logger.info(f"container {self.my_container.name} stopped")
        else:
            self.my_logger.info("no any specified containers")
