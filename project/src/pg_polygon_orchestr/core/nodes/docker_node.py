from .node import Node

import docker
import docker.errors
import docker.models.images as docker_images
import docker.models.networks as docker_networks
import docker.models.containers as docker_containers

import sys

from ..configs.node_config import NodeConfig

from ..logger_config.info_filter import INFO_Filter

import logging
import time

from .exec_result import ExecResult

from ..exception.docker_exceptions import *


class DockerNode(Node):
    def __configure_logger(self) -> None:
        self.my_logger = logging.getLogger(f"docker_node_{self.__name}")

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
        image: docker_images.Image,
        config: NodeConfig,
        name: str,
        default_net: bool,
        networks: list[docker_networks.Network] = [],
    ) -> None:
        self.__my_session = docker_client
        self.__my_image = image
        self.__my_config = config
        self.__my_container: docker_containers.Container | None = None
        self.__my_networks: list[docker_networks.Network] = networks.copy()
        self.__default_net = default_net
        self.__name = name
        self.__cpu_period_default = 100000
        self.__connected_networks = 0  # этот параметр используется для отключения от сетей во время уничтожения (может быть подключены не все сети)
        self.__configure_logger()

    # запуск контейнера (первый запуск - из образа + подключаемся к сети)
    def start(self) -> None:
        if self.__my_container is None:
            self.my_logger.info(
                f"starting a new container from the image {self.__my_image}"
            )

            container_name = self.__name

            try:
                self.__my_container = self.__my_session.containers.run(
                    self.__my_image,
                    cpu_period=self.__cpu_period_default,
                    cpu_quota=self.__cpu_period_default * self.__my_config.cpu_limit,
                    mem_limit=self.__my_config.ram_limit,
                    detach=True,
                    name=container_name,
                    network_disabled=(
                        True
                        if not (self.__my_networks) and not (self.__default_net)
                        else False
                    ),
                    network=(
                        None
                        if self.__default_net
                        else (
                            None
                            if not (self.__my_networks)
                            else self.__my_networks[0].name
                        )
                    ),
                )

                self.my_logger.info(
                    f"new container is running. Its' image - {self.__my_image}"
                )

                if not self.__default_net and self.__my_networks:
                    self.__connected_networks += 1
                    start_connecting = 1
                else:
                    start_connecting = 0

                for net_obj_idx in range(start_connecting, len(self.__my_networks)):
                    net_obj = self.__my_networks[net_obj_idx]
                    try:
                        self.__connect_to_network(net_obj=net_obj)
                        self.__connected_networks += 1
                    except CannotConnectToTheNetwork as err:
                        raise ConnectFunctionError(
                            f"cannot connect to the network {net_obj.name}: {err}"
                        ) from err

            except docker.errors.ContainerError as err:
                self.my_logger.error(
                    f"container {container_name} exited with non-zero code: {err}"
                )

                raise ContainerErrorDuringRunning(
                    f"container {container_name} exited with non-zero code: {err}"
                ) from err
            except docker.errors.ImageNotFound as err:
                self.my_logger.warning(f"cannot find image {self.__my_image}: {err}")
                self.__my_container = None

                raise CannotFindImageToRunAContainer(
                    f"cannot find image {self.__my_image}: {err}"
                )
            except docker.errors.APIError as err:
                self.my_logger.error(f"server returns an error {err}")
                self.__my_container = None

                raise DockerNodeAPIErrorOrccursException(
                    f"failed to run a container from image {self.__my_image}: {err}"
                ) from err

        else:
            self.my_logger.info(f"starting the container {self.__my_container.name}")

            try:
                self.__my_container.start()
            except docker.errors.APIError as err:
                self.my_logger.error(
                    f"failed to start the container {self.__my_container.name}: {err}"
                )

                raise DockerNodeAPIErrorOrccursException(
                    f"failed to start the container {self.__my_container.name}: {err}"
                ) from err

            self.my_logger.info(f"the container {self.__my_container.name} is running")

    # остановка контейнера с таймаутом
    def stop(self, timeout: int) -> None:
        if self.__my_container is not None:
            self.my_logger.info(f"stopping the container {self.__my_container.name}")

            try:
                self.__my_container.reload()
                if self.__my_container.status == "running":
                    self.__my_container.stop(timeout=timeout)
                else:
                    self.my_logger.info(
                        f"container {self.__my_container.name} was already stopped"
                    )
            except docker.errors.APIError as err:
                raise DockerNodeAPIErrorOrccursException(
                    f"cannot stop the container {self.__my_container.name}: {err}"
                ) from err

            self.my_logger.info(f"container {self.__my_container.name} stopped")

            return
        else:
            self.my_logger.info("no any specified containers")

            return

    # исполнение команды
    def exec(self, command: str) -> ExecResult | None:
        if self.__my_container is None:
            return None

        try:
            self.__my_container.reload()  # type: ignore

            if self.__my_container.status != "running":
                raise CannotExecACommandOnNotRunningContainer(
                    f"cannot run the command {command} on the not running container {self.__my_container.name}"
                )

            start = time.perf_counter_ns()
            result = self.__my_container.exec_run(command, demux=True)
            end = time.perf_counter_ns()

            exit_code = result.exit_code
            stdout, stderr = result.output
            execution_time = end - start

            return ExecResult(
                exit_code,
                stdout=stdout.decode(encoding="utf-8") if stdout is not None else "",  # type: ignore
                stderr=stderr.decode(encoding="utf-8") if stderr is not None else "",  # type: ignore
                execution_time=execution_time,
            )
        except docker.errors.APIError:
            raise DockerNodeAPIErrorOrccursException(
                f"cannot execute the command {command} on the container {self.__my_container.name}"
            )

    # метод обновление конфигурации
    def update_configuration(self, new_config: NodeConfig) -> None:
        if self.__my_container is None:
            raise NoDockerContainerToPerformOperation("no any docker container")

        if new_config.cpu_limit <= 0:
            self.my_logger.error(
                f"cannot update {self.__my_container.name}, because cpu_limit <= 0"
            )

            raise UpdateConfigurationCannotBePerfomedIfCpuLimitNotPositive(
                f"cannot update {self.__my_container.name}, because cpu_limit <= 0"
            )

        try:
            self.__my_container.update(  # type: ignore
                mem_limit=new_config.ram_limit,
                cpu_period=self.__cpu_period_default,
                cpu_quota=new_config.cpu_limit * self.__cpu_period_default,
            )

            self.__my_config = new_config

        except docker.errors.APIError as err:
            self.my_logger.error(f"server returns an error")

            raise DockerNodeAPIErrorOrccursException(
                f"server returns an error: {err}"
            ) from err

    # мягкое уничтожение контейнера
    def soft_destroy_container(self) -> None:
        if self.__my_container is not None:
            self.my_logger.info(f"destroying the container {self.__my_container.name}")

            try:
                self.__my_container.reload()

                if self.__my_container.status == "running":
                    for net_obj in self.__my_networks:
                        self.__disconnect_from_network(net_obj=net_obj)

                        self.__connected_networks -= 1
                        if not (self.__connected_networks):
                            break

                    self.__my_container.stop(timeout=1)
                else:
                    for (
                        net_obj
                    ) in (
                        self.__my_networks
                    ):  # если контейнер не запущен, то тогда мы принуждаем его отключиться от сети
                        self.__disconnect_from_network(net_obj=net_obj, force=True)

                        self.__connected_networks -= 1
                        if not (self.__connected_networks):
                            break

                self.__my_container.remove(v=True)
            except docker.errors.APIError as err:

                self.my_logger.error(f"server returns an error {err}")
                raise DockerNodeAPIErrorOrccursException(
                    f"an error occurs: {err}"
                ) from err

            except CannotDisconnectFromTheNetwork as err:

                raise DisonnectFunctionError(
                    f"cannot perform disconnection: {err}"
                ) from err

            self.__my_container = None
        else:
            self.my_logger.info("no any specified containers")

    # грубое уничтожение контейнера
    def force_destroy_container(self) -> None:
        if self.__my_container is None:
            return

        try:
            for net_obj in self.__my_networks:
                self.__disconnect_from_network(net_obj=net_obj, force=True)

                self.__connected_networks -= 1
                if not (self.__connected_networks):
                    break

            self.__my_container.remove(v=True, force=True)
        except docker.errors.APIError as err:
            self.my_logger.error(
                f"cannot force delete container {self.__my_container.name}"
            )

            raise DockerNodeAPIErrorOrccursException(
                f"cannot force delete container {self.__my_container.name}: {err}"
            ) from err
        except CannotDisconnectFromTheNetwork as err:
            raise DisonnectFunctionError(
                f"cannot perform disconnection: {err}"
            ) from err

        self.__my_container = None

    # приватный метод ПОДКЛЮЧЕНИЯ к сети
    def __connect_to_network(self, net_obj: docker_networks.Network) -> None:
        if self.__my_container is None:
            raise NoDockerContainerToPerformOperation("no any docker container")

        try:
            net_obj.connect(self.__my_container)  # type: ignore
        except docker.errors.APIError as err:
            raise CannotConnectToTheNetwork(
                f"conrainer {self.__my_container.name} cannot connect to the network {net_obj.name} because of this error: {err}"
            ) from err

    # приватный метод ОТКЛЮЧЕНИЯ от сети
    def __disconnect_from_network(
        self, net_obj: docker_networks.Network, force: bool = False
    ) -> None:
        if self.__my_container is None:
            raise NoDockerContainerToPerformOperation("no any docker container")

        try:
            net_obj.disconnect(self.__my_container, force=force)
        except docker.errors.APIError as err:
            raise CannotDisconnectFromTheNetwork(
                f"the container {self.__my_container.name} cannot disconnect from the network {net_obj.name}: {err}"
            ) from err

    # ГЕТТЕРЫ для ноды
    def get_name(self) -> str:
        return self.__name

    def current_cpu_limit(self) -> int:
        return self.__my_config.cpu_limit

    def current_mem_limit(self) -> str:
        return self.__my_config.ram_limit

    def get_os(self) -> str:
        return self.__my_config.os_name
