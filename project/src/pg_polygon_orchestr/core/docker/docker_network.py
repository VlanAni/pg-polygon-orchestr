from ..interfaces import network, entity_state, types
from ..configs import net_config
from . import docker_deployer, docker_node
from ..exception import docker_exceptions, common_exceptions

import docker.errors
import typing


class DockerNetwork(network.Network):
    def __init__(
        self,
        name: str,
        config: net_config.NetConfig,
        deployer: docker_deployer.DockerDeployer,
    ):
        self.__name = name
        self.__config = config
        self.__deployer = deployer
        self.__state = entity_state.EntityState.NOT_DEPLOYED
        self.__network = None

    # ------ интерфейсные методы

    def get_name(self) -> str:
        return self.__name

    def get_type(self) -> types.Type:
        return types.Type.DOCKER

    def deploy(self) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__name} is removed"
            )

        if self.__is_state_as_required(required=entity_state.EntityState.DEPLOYED):
            raise common_exceptions.EntityIsAlreadyDeployed(
                f"the network {self.__name} is already deployed"
            )

        self.__deploy()

    def clear(self) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__name} is removed"
            )

        if self.__is_state_as_required(required=entity_state.EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the network {self.__name} is not deployed"
            )

        self.__clear()

    def remove(self) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__name} is removed"
            )

        self.__remove()

    def get_network_ip(self) -> str:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__name} is removed"
            )

        if self.__is_state_as_required(required=entity_state.EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the network {self.__name} is not deployed"
            )

        self.__network.reload()  # type: ignore

        if self.__network.attrs["IPAM"]["Config"] is None or []:  # type: ignore
            raise docker_exceptions.GetDockerNetIpError(
                f"the network {self.__name} has an empty IPAM config"
            )

        return self.__network.attrs["IPAM"]["Config"][0]["Subnet"]  # type: ignore

    def connect_node(self, node: network.Node) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__name} is removed"
            )

        if self.__is_state_as_required(required=entity_state.EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the network {self.__name} is not deployed"
            )

        self.__connect_node(node=node)

    def disconnect_node(self, node: network.Node) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__name} is removed"
            )

        if self.__is_state_as_required(required=entity_state.EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the network {self.__name} is not deployed"
            )

        self.__disconnect_node(node=node)

    def get_node_network_ip(self, node: network.Node, ipv6: bool = False) -> str:
        if self.__is_state_as_required(required=entity_state.EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__name} is removed"
            )

        if self.__is_state_as_required(required=entity_state.EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the network {self.__name} is not deployed"
            )

        return self.__get_node_network_ip(node=node, ipv6=ipv6)

    # ------ приватные коллбэки

    def __deploy(self) -> None:
        try:
            network = self.__deployer.create_network(who_ask=self, config=self.__config)  # type: ignore
        except docker_exceptions.ResourceCreationError as err:
            raise docker_exceptions.DockerDeployError(
                f"failed to create a docker network {self.__name}"
            ) from err

        if network is None:
            raise docker_exceptions.DockerDeployError(
                f"failed to create a docker network {self.__name} because it is not registred"
            )

        self.__network = network
        self.__state = entity_state.EntityState.DEPLOYED

    def __clear(self) -> None:
        try:
            self.__network.remove()  # type: ignore
        except docker.errors.APIError as err:
            raise docker_exceptions.DockerClearError(
                f"cannot remove the network {self.__name}"
            ) from err

        self.__network = None
        self.__state = entity_state.EntityState.NOT_DEPLOYED

    def __remove(self) -> None:
        if self.__is_state_as_required(required=entity_state.EntityState.DEPLOYED):
            try:
                self.__network.remove()  # type: ignore
            except docker.errors.APIError as err:
                raise docker_exceptions.DockerClearError(
                    f"cannot remove the network {self.__name}"
                ) from err

        self.__deployer.remove_network(who_ask=self)  # type: ignore

        self.__network = None
        self.__state = entity_state.EntityState.REMOVED
        self.__deployer = None
        self.__config = None

    def __connect_node(self, node: network.Node) -> None:
        if node.get_type() is types.Type.DOCKER:
            d_node = typing.cast(docker_node.DockerNode, val=node)
        else:
            raise docker_exceptions.ConnectToDockerNetError(
                f"the node {node.get_name()} is not a docker node"
            )

        known = self.__deployer.check_node_is_known(who_ask=self, node=d_node)  # type: ignore

        if known is None:
            raise docker_exceptions.ConnectToDockerNetError(
                f"the network {self.__name} is not registred"
            )
        if not known:
            raise docker_exceptions.ConnectToDockerNetError(
                f"the node {d_node.get_name()} is not registred"
            )

        container_id = d_node.share_container_id()

        if container_id is None:
            raise docker_exceptions.ConnectToDockerNetError(
                f"the node {d_node.get_name()} doesn't have alive container. Maybe removed / not_deployer / hasn't been started"
            )

        try:
            self.__network.connect(container=container_id)  # type: ignore
        except docker.errors.APIError as err:
            raise docker_exceptions.ConnectToDockerNetError(
                f"failed to connect the container {d_node.get_name()} with id {container_id} to the network {self.__name}"
            ) from err

    def __disconnect_node(self, node: network.Node) -> None:
        if node.get_type() is types.Type.DOCKER:
            d_node = typing.cast(docker_node.DockerNode, val=node)
        else:
            raise docker_exceptions.ConnectToDockerNetError(
                f"the node {node.get_name()} is not a docker node"
            )

        known = self.__deployer.check_node_is_known(who_ask=self, node=d_node)  # type: ignore

        if known is None:
            raise docker_exceptions.ConnectToDockerNetError(
                f"the network {self.__name} is not registred"
            )
        if not known:
            raise docker_exceptions.ConnectToDockerNetError(
                f"the node {d_node.get_name()} is not registred"
            )

        container_id = d_node.share_container_id()

        if container_id is None:
            raise docker_exceptions.ConnectToDockerNetError(
                f"the node {d_node.get_name()} doesn't have alive container. Maybe removed / not_deployer / hasn't been started"
            )

        try:
            self.__network.disconnect(container=container_id)  # type: ignore
        except docker.errors.APIError as err:
            raise docker_exceptions.ConnectToDockerNetError(
                f"failed to disconnect the container {d_node.get_name()} with id {container_id} from the network {self.__name}"
            ) from err

    def __get_node_network_ip(self, node: network.Node, ipv6: bool = False) -> str:
        if node.get_type() is types.Type.DOCKER:
            d_node = typing.cast(docker_node.DockerNode, val=node)
        else:
            raise docker_exceptions.GetContainerIpError(
                f"the node {node.get_name()} is not a docker node"
            )

        known = self.__deployer.check_node_is_known(who_ask=self, node=d_node)  # type: ignore

        if known is None:
            raise docker_exceptions.GetContainerIpError(
                f"the network {self.__name} is not registred"
            )
        if not known:
            raise docker_exceptions.GetContainerIpError(
                f"the node {d_node.get_name()} is not registred"
            )

        container_id = d_node.share_container_id()

        if container_id is None:
            raise docker_exceptions.GetContainerIpError(
                f"the node {d_node.get_name()} doesn't have alive container. Maybe removed / not_deployer / hasn't been started"
            )

        self.__network.reload()  # type: ignore

        containers = self.__network.attrs.get("Containers", None)  # type: ignore

        if containers is None or containers == {}:
            raise docker_exceptions.GetContainerIpError(
                f"the network {self.__name} doesn't have any containers"
            )

        containers = typing.cast(dict[str, typing.Any], containers)

        cont_data = containers.get(container_id, None)

        if cont_data is None or cont_data == {}:
            raise docker_exceptions.GetContainerIpError(
                f"the container {container_id} isn't attached to the network {self.__name}"
            )

        cont_data = typing.cast(dict[str, str], cont_data)

        if ipv6:
            ipv6_address = cont_data.get("IPv6Address", "")
            if not ipv6_address:
                raise docker_exceptions.GetContainerIpError(
                    f"the container {container_id} doesn't have an ipv6-address in the network {self.__name}"
                )
            result = ipv6_address
        else:
            ipv4_address = cont_data.get("IPv4Address", "")
            if not ipv4_address:
                raise docker_exceptions.GetContainerIpError(
                    f"the container {container_id} doesn't have an ipv4-address in the network {self.__name}"
                )
            result = ipv4_address

        return result.split("/")[0]

    # ------ приватные методы

    def __is_state_as_required(self, required: entity_state.EntityState) -> bool:
        return self.__state == required
