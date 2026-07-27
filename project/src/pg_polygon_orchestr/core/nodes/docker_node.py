from .node import Node

import docker
import docker.errors
import docker.models.images

import sys

from ..configs.node_config import NodeConfig

from ..logger_config.info_filter import INFO_Filter

import logging


class DockerNode(Node):
    def __configure_logger(self) -> None:
        self.my_logger = logging.getLogger(f"docker_node_{self.__id}")

        self.my_logger.setLevel(logging.INFO)

        if self.my_logger.handlers:
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

        self.my_logger.addHandler(info_handler)
        self.my_logger.addHandler(trouble_handler)

    def __init__(
        self,
        docker_client: docker.DockerClient,
        image: docker.models.images.Image,
        config: NodeConfig,
        id: int,
    ) -> None:
        self.__my_session = docker_client
        self.__my_image = image
        self.__my_config = config
        self.__my_container = None
        self.__id = id
        self.__configure_logger()

    def start(self) -> bool:
        if self.__my_container is None:
            self.my_logger.info(
                f"starting a new container from the image {self.__my_image}"
            )

            container_name = f"docker_node_{self.__id}_container"

            try:
                self.__my_container = self.__my_session.containers.run(
                    self.__my_image.tags[0],
                    nano_cpus=int(
                        self.__my_config.cpu_limit * 1e9
                    ),  # do mult with cpu_limit and 1e-9 to get nanocpu-limit (it's universal)
                    mem_limit=self.__my_config.ram_limit,  # hard limit for how many memory our container can use
                    detach=True,  # set detach as True to make .run non-block...
                    name=container_name,
                )
            except docker.errors.ContainerError:
                self.my_logger.error(
                    f"container {container_name} exited with non-zero code"
                )
                return False
            except docker.errors.ImageNotFound:
                self.my_logger.warning(f"cannot find image {self.__my_image}")
                self.__my_container = None
                return False
            except docker.errors.APIError:
                self.my_logger.error(f"server returns an error")
                self.__my_container = None
                return False

            self.my_logger.info(
                f"new container is running. Its' image - {self.__my_image}"
            )

            return True
        else:
            self.my_logger.info(f"starting the container {self.__my_container.name}")

            try:
                self.__my_container.start()
            except docker.errors.APIError:
                self.my_logger.error(f"server returns an error")
                return False

            self.my_logger.info(f"the container {self.__my_container.name} is running")

            return True

    def stop(self, timeout: int) -> bool:
        if self.__my_container is not None:
            self.my_logger.info(f"stopping the container {self.__my_container.name}")

            try:
                self.__my_container.reload()
                if self.__my_container.status == "running":
                    self.__my_container.stop(timeout=timeout)
            except docker.errors.APIError:
                self.my_logger.error(f"server returns an error")
                return False

            self.my_logger.info(f"container {self.__my_container.name} stopped")

            return True
        else:
            self.my_logger.info("no any specified containers")

            return False

    def clearContainer(self) -> None:
        if self.__my_container is not None:
            self.my_logger.info(f"destroying the container {self.__my_container.name}")

            try:
                self.__my_container.reload()
                if self.__my_container.status != "running":
                    self.__my_container.remove(v=True)
            except docker.errors.APIError:
                self.my_logger.error(f"server returns an error")
                return

            self.__my_container = None
        else:
            self.my_logger.info("no any specified containers")
