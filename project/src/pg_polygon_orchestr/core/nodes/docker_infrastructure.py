from .infrastructure import Infrastructure
from .docker_node import DockerNode
from ..configs.node_config import NodeConfig
from ..exception import docker_exceptions
from ..exception import common_exceptions
from .exec_result import ExecResult

from docker.models import networks as docker_networks


class DockerInfrastructure(Infrastructure):

    def __init__(
        self,
        nodes: list[DockerNode],
        networks: list[docker_networks.Network] | None = None,
    ) -> None:
        self.__nodes = self.__init_nodes_dict(nodes)
        self.__usable = True
        self.__networks = (
            {} if networks is None else self.__init_network_dict(networks=networks)
        )

    def __init_nodes_dict(self, nodes: list[DockerNode]) -> dict[str, DockerNode]:
        nodes_dict: dict[str, DockerNode] = dict()

        for node in nodes:
            nodes_dict[node.get_name()] = node

        return nodes_dict

    def __init_network_dict(
        self, networks: list[docker_networks.Network]
    ) -> dict[str, docker_networks.Network]:
        net_dict: dict[str, docker_networks.Network] = dict()

        for net_obj in networks:
            net_dict[net_obj.name] = net_obj  # type: ignore

        return net_dict

    def start(self) -> None:

        if not (self.__usable):
            return

        node_names = list(self.__nodes.keys())

        for node_name in node_names:
            try:
                node = self.__nodes[node_name]
                node.start()
            except docker_exceptions.DockerNodeAPIErrorOrccursException as err:

                raise common_exceptions.FailedToStartNodeFromInfrastructureException(
                    f"docker api sends error during starting node {node_name}: {err}"
                ) from err

            except docker_exceptions.ConnectFunctionError as err:

                raise common_exceptions.FailedToStartNodeFromInfrastructureException(
                    f"connection error during starting node {node_name}: {err}"
                ) from err

            except docker_exceptions.ContainerErrorDuringRunning as err:

                raise common_exceptions.FailedToStartNodeFromInfrastructureException(
                    f"container returns errors during starting node {node_name}: {err}"
                ) from err

            except docker_exceptions.CannotFindImageToRunAContainer as err:

                raise common_exceptions.FailedToStartNodeFromInfrastructureException(
                    f"cannot find image to run a container {node_name}: {err}"
                ) from err

    def stop(self, timeout: int) -> None:
        if not (self.__usable):
            return

        for node_name in self.__nodes.keys():
            try:
                node = self.__nodes[node_name]
                node.stop(timeout=timeout)
            except docker_exceptions.DockerNodeAPIErrorOrccursException as err:

                raise common_exceptions.FailedToStopInfrastructure(
                    f"failed to stop the node {node_name}: {err}"
                )

    def exec_command_on_node(self, node_name: str, command: str) -> ExecResult | None:
        if not (self.__usable):
            return

        node = self.__nodes.get(node_name, None)

        if node is None:

            raise common_exceptions.FailedToExecuteCommand(
                f"there is no node with the name {node_name}"
            )

        try:
            result = node.exec(command=command)
            return result
        except docker_exceptions.CannotExecACommandOnNotRunningContainer as err:

            raise common_exceptions.FailedToExecuteCommand(
                f"the node {node_name} hasn't its running container: {err}"
            )

        except docker_exceptions.DockerNodeAPIErrorOrccursException as err:

            raise common_exceptions.FailedToExecuteCommand(
                f"failed to execute a command because of API error: {err}"
            )

    def mask_as_unusable(self) -> None:
        self.__usable = False

    def get_usable(self) -> bool:
        return self.__usable

    def get_nodes(self) -> dict[str, DockerNode]:
        return self.__nodes.copy()

    def update_configuration(self, new_config: NodeConfig, node_name: str) -> None:
        if not (self.__usable):
            return

        node = self.__nodes.get(node_name, None)
        if node is None:

            raise common_exceptions.FailedToFindANodeWithByItsName(
                f"cannot find a node with the name {node_name}"
            )

        try:
            node.update_configuration(new_config=new_config)
        except docker_exceptions.NoDockerContainerToPerformOperation as err:

            raise common_exceptions.FailedToUpdateConfiguration(
                f"node {node_name} doesn't have a container"
            ) from err

        except (
            docker_exceptions.UpdateConfigurationCannotBePerfomedIfCpuLimitNotPositive
        ) as err:

            raise common_exceptions.FailedToUpdateConfiguration(
                f"wrong params to update"
            ) from err

        except docker_exceptions.DockerNodeAPIErrorOrccursException as err:

            raise common_exceptions.FailedToUpdateConfiguration(
                f"failed to update {node_name}'s configuration"
            ) from err

    def get_network_ip_addr(self, net_name: str) -> str | None:

        net_obj = self.__networks.get(net_name, None)

        if net_obj is None:
            return None

        net_obj.reload()

        if net_obj.attrs["IPAM"]["Config"] is None or []:
            return None

        return net_obj.attrs["IPAM"]["Config"][0]["Subnet"]

    def get_node_ip_in_network(self, node_name: str, net_name: str) -> str | None:

        node = self.__nodes.get(node_name, None)

        if node is None:
            return None

        return node.get_node_network_ip(net_name=net_name)
