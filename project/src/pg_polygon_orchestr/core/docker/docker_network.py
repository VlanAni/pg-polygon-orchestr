from ..abstract import Network, Node, EntityRegistry
from ..configs import NetConfig
from . import docker_session, docker_node
from ..exception import docker_exceptions, common_exceptions

import docker.errors
import typing
import uuid

from ..meta import EntityState, Type


class DockerNetwork(Network):
    def __init__(
        self,
        name: str,
        config: NetConfig,
        session: docker_session.DockerClientSession,
        shared_node_registry: EntityRegistry,
        id: uuid.UUID | None = None,
    ):
        self.__inf_name = name
        self.__config = config
        self.__clsession = session
        self.__state = EntityState.NOT_DEPLOYED
        self.__dnet = None
        self.__uuid: uuid.UUID = uuid.uuid4() if id is None else id
        self.__shared_nodes: EntityRegistry = shared_node_registry
        self.__n_uuids: dict[uuid.UUID, bool] = dict()
        self.__real_name = str(self.__uuid)

    # ------ интерфейсные методы

    def inf_name(self) -> str:
        return self.__inf_name

    def get_type(self) -> Type:
        return Type.DOCKER

    def get_id(self) -> uuid.UUID:
        return self.__uuid

    def deploy(self, **options: str) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.DEPLOYED):
            raise common_exceptions.EntityIsAlreadyDeployed(
                f"the network {self.__inf_name} is already deployed"
            )

        self.__deploy(options=options)

    def clear(self) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the network {self.__inf_name} is not deployed"
            )

        self.__clear()

    def remove(self) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__inf_name} is removed"
            )

        self.__remove()

    def get_network_ip(self, ipv6: bool = False) -> str:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the network {self.__inf_name} is not deployed"
            )

        self.__dnet.reload()  # type: ignore

        if self.__dnet.attrs["IPAM"]["Config"] is None or []:  # type: ignore
            raise docker_exceptions.GetDockerNetIpError(
                f"the network {self.__inf_name} has an empty IPAM config"
            )

        for ipam_config in self.__dnet.attrs["IPAM"]["Config"]:  # type: ignore
            ip_addr = ipam_config["Subnet"]

            if ":" in ip_addr and ipv6:
                return ip_addr
            elif "." in ip_addr and not (ipv6):
                return ip_addr

        raise docker_exceptions.GetDockerNetIpError(
            f"failed to find ip-address in the network {self.__inf_name}"
        )

    def connect_node(
        self, node: Node, ipv4_addr: str | None = None, ipv6_addr: str | None = None
    ) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the network {self.__inf_name} is not deployed"
            )

        self.__connect_node(node=node, ipv4_addr=ipv4_addr, ipv6_addr=ipv6_addr)

    def disconnect_node(self, node: Node) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the network {self.__inf_name} is not deployed"
            )

        self.__disconnect_node(node=node)

    def get_node_network_ip(self, node: Node, ipv6: bool = False) -> str:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the network {self.__inf_name} is not deployed"
            )

        return self.__get_node_network_ip(node=node, ipv6=ipv6)

    def transform_to_mapping(self) -> typing.Mapping[str, typing.Any]:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.TryToSerializeRemovedEntity(
                f"the volume {self.__inf_name} is removed"
            )

        try:
            return {
                "type": Type.DOCKER,
                "uuid": self.__uuid,
                "name": self.__inf_name,
                "state": self.__state,
                "network-ip": (
                    self.get_network_ip()
                    if self.__is_state_as_required(required=EntityState.DEPLOYED)
                    else None
                ),
                "gateway-ip": (
                    self.__extract_gateway_addr()
                    if self.__is_state_as_required(required=EntityState.DEPLOYED)
                    else None
                ),
                "connected_nodes": self.__serialyze_connected_nodes(),
                "config": self.__config,
            }
        except common_exceptions.MakeSnapshotError as err:
            raise common_exceptions.MakeSnapshotError(
                f"cannot serialize the network {self.__inf_name}"
            ) from err

    def real_name(self) -> str:
        return self.__real_name

    def state(self) -> EntityState:
        return self.__state

    # ------ приватные коллбэки

    def __deploy(self, options: dict[str, str]) -> None:
        subnet_ip = options.get("ip", "")
        static_gateway_ip = options.get("gateway", "")

        if bool(subnet_ip) != bool(static_gateway_ip):
            raise docker_exceptions.DockerDeployError(
                f"if you want to deploy a network with static ip, you must pass its ip and its gateway ip"
            )

        try:
            network = self.__clsession.ask_to_create_network(
                name=str(self.__uuid),
                config=self.__config,  # type: ignore
                ip=subnet_ip if subnet_ip else None,
                gateway_ip=static_gateway_ip if static_gateway_ip else None,
            )
        except docker_exceptions.ResourceCreationError as err:
            raise docker_exceptions.DockerDeployError(
                f"failed to create a docker network {self.__inf_name}"
            ) from err

        if network is None:
            raise docker_exceptions.DockerDeployError(
                f"failed to create a docker network {self.__inf_name} because it is not registred"
            )

        self.__dnet = network
        self.__state = EntityState.DEPLOYED

    def __clear(self) -> None:
        try:
            self.__dnet.remove()  # type: ignore
        except docker.errors.APIError as err:
            raise docker_exceptions.DockerClearError(
                f"cannot remove the network {self.__inf_name}"
            ) from err

        self.__dnet = None
        self.__n_uuids.clear()
        self.__state = EntityState.NOT_DEPLOYED

    def __remove(self) -> None:
        if self.__is_state_as_required(required=EntityState.DEPLOYED):
            try:
                self.__dnet.remove()  # type: ignore
            except docker.errors.APIError as err:
                raise docker_exceptions.DockerClearError(
                    f"cannot remove the network {self.__inf_name}"
                ) from err

        self.__dnet = None
        self.__state = EntityState.REMOVED
        self.__n_uuids.clear()
        self.__config = None

    def __connect_node(
        self, node: Node, ipv4_addr: str | None = None, ipv6_addr: str | None = None
    ) -> None:
        if node.get_type() is Type.DOCKER:
            d_node = typing.cast(docker_node.DockerNode, val=node)
        else:
            raise docker_exceptions.ConnectToDockerNetError(
                f"the node {node.inf_name()} is not a docker node"
            )

        if self.__shared_nodes.get_entity_by_id(uuid=d_node.get_id()) is None:
            raise docker_exceptions.ConnectToDockerNetError(
                f"the node {d_node.inf_name()} with id {d_node.get_id()} is not known"
            )

        if self.__n_uuids.get(d_node.get_id(), None) is not None:
            raise docker_exceptions.ConnectToDockerNetError(
                f"the node {d_node.inf_name()} with id {d_node.get_id()} is already connected"
            )

        if node.state() != EntityState.DEPLOYED:
            raise docker_exceptions.ConnectToDockerNetError(
                f"the node {d_node.inf_name()} with id {d_node.get_id()} is not deployed"
            )

        container_id = d_node.share_container_id()

        if container_id is None:
            raise docker_exceptions.ConnectToDockerNetError(
                f"the node {d_node.inf_name()} doesn't have alive container. Maybe removed / not_deployer / hasn't been started"
            )

        ipv4_addr_validated = None if not (self.__config.ipv4) else ipv4_addr  # type: ignore
        ipv6_addr_validated = None if not (self.__config.ipv6) else ipv6_addr  # type: ignore

        try:
            self.__dnet.connect(container=container_id, ipv4_address=ipv4_addr_validated, ipv6_address=ipv6_addr_validated)  # type: ignore
            self.__n_uuids[d_node.get_id()] = True
        except docker.errors.APIError as err:
            raise docker_exceptions.ConnectToDockerNetError(
                f"failed to connect the container {d_node.inf_name()} with id {container_id} to the network {self.__inf_name}"
            ) from err

    def __disconnect_node(self, node: Node) -> None:
        if node.get_type() is Type.DOCKER:
            d_node = typing.cast(docker_node.DockerNode, val=node)
        else:
            raise docker_exceptions.DisconnectFromDockerNetError(
                f"the node {node.inf_name()} is not a docker node"
            )

        if self.__shared_nodes.get_entity_by_id(d_node.get_id()) is None:
            raise docker_exceptions.DisconnectFromDockerNetError(
                f"the node {d_node.inf_name()} with id {d_node.get_id()} is not known"
            )

        if self.__n_uuids.get(d_node.get_id(), None) is None:
            raise docker_exceptions.DisconnectFromDockerNetError(
                f"the node {d_node.inf_name()} with id {d_node.get_id()} is already disconnected"
            )

        if node.state() != EntityState.DEPLOYED:
            self.__n_uuids.pop(d_node.get_id())
            raise docker_exceptions.DisconnectFromDockerNetError(
                f"the node {d_node.inf_name()} with id {d_node.get_id()} is not deployed"
            )

        container_id = d_node.share_container_id()

        if container_id is None:
            raise docker_exceptions.DisconnectFromDockerNetError(
                f"the node {d_node.inf_name()} doesn't have alive container. Maybe removed / not_deployer / hasn't been started"
            )

        try:
            self.__dnet.disconnect(container=container_id)  # type: ignore
            self.__n_uuids.pop(d_node.get_id())
        except docker.errors.APIError as err:
            raise docker_exceptions.DisconnectFromDockerNetError(
                f"failed to disconnect the container {d_node.inf_name()} with id {container_id} from the network {self.__inf_name}"
            ) from err

    def __get_node_network_ip(self, node: Node, ipv6: bool = False) -> str:
        if node.get_type() is Type.DOCKER:
            d_node = typing.cast(docker_node.DockerNode, val=node)
        else:
            raise docker_exceptions.GetContainerIpError(
                f"the node {node.inf_name()} is not a docker node"
            )

        if self.__shared_nodes.get_entity_by_id(uuid=d_node.get_id()) is None:
            raise docker_exceptions.GetContainerIpError(
                f"the node {d_node.inf_name()} with id {d_node.get_id} is not known"
            )

        if self.__n_uuids.get(d_node.get_id(), None) is None:
            raise docker_exceptions.GetContainerIpError(
                f"the node {d_node.inf_name()} with id {d_node.get_id()} is disconnected"
            )

        if d_node.state() != EntityState.DEPLOYED:
            self.__n_uuids.pop(d_node.get_id())
            raise docker_exceptions.GetContainerIpError(
                f"the node {d_node.inf_name()} with id {d_node.get_id()} is removed"
            )

        container_id = d_node.share_container_id()

        if container_id is None:
            raise docker_exceptions.GetContainerIpError(
                f"the node {d_node.inf_name()} doesn't have alive container"
            )

        self.__dnet.reload()  # type: ignore

        containers = self.__dnet.attrs.get("Containers", None)  # type: ignore

        if containers is None or containers == {}:
            raise docker_exceptions.GetContainerIpError(
                f"the network {self.__inf_name} doesn't have any containers"
            )

        containers = typing.cast(dict[str, typing.Any], containers)

        cont_data = containers.get(container_id, None)

        if cont_data is None or cont_data == {}:
            raise docker_exceptions.GetContainerIpError(
                f"the container {container_id} isn't attached to the network {self.__inf_name}"
            )

        cont_data = typing.cast(dict[str, str], cont_data)

        if ipv6:
            ipv6_address = cont_data.get("IPv6Address", "")
            if not ipv6_address:
                raise docker_exceptions.GetContainerIpError(
                    f"the container {container_id} doesn't have an ipv6-address in the network {self.__inf_name}"
                )
            result = ipv6_address
        else:
            ipv4_address = cont_data.get("IPv4Address", "")
            if not ipv4_address:
                raise docker_exceptions.GetContainerIpError(
                    f"the container {container_id} doesn't have an ipv4-address in the network {self.__inf_name}"
                )
            result = ipv4_address

        return result.split("/")[0]

    # ------ приватные методы

    def __is_state_as_required(self, required: EntityState) -> bool:
        return self.__state == required

    def __serialyze_connected_nodes(self) -> dict[str, dict[str, str]] | None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            return None

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            return None

        result: dict[str, dict[str, str]] = dict()

        for node_uuid in self.__n_uuids.keys():
            node = self.__shared_nodes.get_entity_by_id(uuid=node_uuid)
            node = typing.cast(docker_node.DockerNode, node)

            if node.state() != EntityState.DEPLOYED:
                self.__n_uuids.pop(node_uuid)
                continue

            if not (self.__config.ipv4):  # type: ignore
                ipv4 = ""
            else:
                try:
                    ipv4 = self.__get_node_network_ip(node=node)
                except docker_exceptions.GetContainerIpError:
                    ipv4 = ""

            if not (self.__config.ipv6):  # type: ignore
                ipv6 = ""
            else:
                try:
                    ipv6 = self.__get_node_network_ip(node=node, ipv6=True)
                except docker_exceptions.GetContainerIpError:
                    ipv6 = ""

            result[str(node_uuid)] = {"ipv4": ipv4, "ipv6": ipv6}

        return result

    def __extract_gateway_addr(self) -> str:
        if self.__dnet is None:
            return ""

        self.__dnet.reload()

        if self.__dnet.attrs["IPAM"]["Config"] is None or []:
            raise docker_exceptions.GetDockerNetIpError(
                f"the network {self.__inf_name} has an empty IPAM config"
            )

        return self.__dnet.attrs["IPAM"]["Config"][0]["Gateway"]
