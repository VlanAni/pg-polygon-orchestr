from ..abstract import Network, Node, EntityRegistry
from ..configs import NetConfig
from . import docker_session, docker_node
from ..exception import docker_exceptions, common_exceptions

import docker.errors
import typing
import uuid
import ipaddress

from ..meta import (
    EntityState,
    Type,
    SubnetConfig,
    SubnetDesc,
    ConnectionInfo,
    SubnetInfo,
)


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
        self.__connd_node_map: dict[uuid.UUID, ConnectionInfo] = dict()
        self.__subnts_reg: dict[str, SubnetDesc] | None = None
        self.__real_name = str(self.__uuid)

    # ------ интерфейсные методы

    def inf_name(self) -> str:
        return self.__inf_name

    def get_type(self) -> Type:
        return Type.DOCKER

    def get_id(self) -> uuid.UUID:
        return self.__uuid

    def deploy(self, **options: list[SubnetConfig]) -> None:
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

    def subnets(self) -> list[SubnetInfo]:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the network {self.__inf_name} is not deployed"
            )

        return [
            SubnetInfo(label=label, subnet=sd.subnet, gateway=sd.gateway)
            for label, sd in self.__subnts_reg.items()  # type: ignore
        ]

    def connect(
        self,
        node: Node,
        subnet_label: str,
        addr: ipaddress.IPv4Address | None = None,
    ) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the network {self.__inf_name} is not deployed"
            )

        self.__connect(node=node, addr=addr, subnet_label=subnet_label)

    def disconnect(self, node: Node) -> None:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the network {self.__inf_name} is not deployed"
            )

        self.__disconnect_node(node=node)

    def get_node_connection_info(self, node: Node) -> ConnectionInfo:
        if self.__is_state_as_required(required=EntityState.REMOVED):
            raise common_exceptions.EntityIsRemovedException(
                f"the network {self.__inf_name} is removed"
            )

        if self.__is_state_as_required(required=EntityState.NOT_DEPLOYED):
            raise common_exceptions.EntityIsNotDeployed(
                f"the network {self.__inf_name} is not deployed"
            )

        return self.__get_node_connection_info(node=node)

    def serialize(self) -> typing.Mapping[str, typing.Any]:
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
                "subnets_data": (self.__subnts_reg),
                "conn_node_map": {
                    str(id): conn_info
                    for id, conn_info in self.__connd_node_map.items()
                },
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

    # ------ функции для управления внутренней работы с docker

    def free_address_of_not_deployed_node(self, node: docker_node.DockerNode):
        conn_info = self.__connd_node_map.get(node.get_id(), None)

        if conn_info is None:
            return

        self.__subnts_reg[conn_info.subnet_label].free_address(addr=conn_info.address)  # type: ignore

    # ------ приватные коллбэки

    def __deploy(self, options: dict[str, list[SubnetConfig]]) -> None:
        subnet_configs = options.get("subnet_configs", None)

        if not subnet_configs:
            raise docker_exceptions.DockerDeployError(
                "there are not any subnets to deploy"
            )

        try:
            network = self.__clsession.ask_to_create_network(
                name=str(self.__uuid),
                config=self.__config,  # type: ignore
                subnet_configs=subnet_configs,
            )
        except docker_exceptions.ResourceCreationError as err:
            raise docker_exceptions.DockerDeployError(
                f"failed to create a docker network {self.__inf_name}"
            ) from err

        self.__dnet = network

        if subnet_configs:
            self.__subnts_reg = {
                sc.label: SubnetDesc(config=sc) for sc in subnet_configs
            }

        self.__state = EntityState.DEPLOYED

    def __clear(self) -> None:
        try:
            self.__dnet.remove()  # type: ignore
        except docker.errors.APIError as err:
            raise docker_exceptions.DockerClearError(
                f"cannot remove the network {self.__inf_name}"
            ) from err

        self.__dnet = None
        self.__connd_node_map.clear()
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
        self.__connd_node_map.clear()
        self.__config = None

    def __connect(
        self,
        node: Node,
        subnet_label: str,
        addr: str | ipaddress.IPv4Address | None = None,
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

        if self.__connd_node_map.get(d_node.get_id(), None) is not None:
            raise docker_exceptions.ConnectToDockerNetError(
                f"the node {d_node.inf_name()} with id {d_node.get_id()} is already connected"
            )

        if node.state() != EntityState.DEPLOYED:
            raise docker_exceptions.ConnectToDockerNetError(
                f"the node {d_node.inf_name()} with id {d_node.get_id()} is not deployed"
            )

        subnet_desc = self.__subnts_reg.get(subnet_label, None)  # type: ignore

        if subnet_desc is None:
            raise docker_exceptions.ConnectToDockerNetError(
                f"there is no the subnet with the label {subnet_label}"
            )

        if isinstance(addr, str):
            try:
                final_addr = ipaddress.IPv4Address(address=addr)
            except Exception as err:
                raise docker_exceptions.ConnectToDockerNetError(
                    f"failed to extract an IP-address from the string {addr}"
                ) from err
        else:
            final_addr = addr

        try:
            allocated_addr = subnet_desc.allocate_address(addr=final_addr)
        except Exception as err:
            raise docker_exceptions.ConnectToDockerNetError(
                f"failed to allocate an IP address in the subnet {subnet_label}"
            ) from err

        container_id = d_node.docker_container_id()

        try:
            if allocated_addr.version == 4:
                self.__dnet.connect(container=container_id, ipv4_address=str(allocated_addr))  # type: ignore
            elif allocated_addr.version == 6:
                self.__dnet.connect(container=container_id, ipv6_address=str(allocated_addr))  # type: ignore
        except docker.errors.APIError as err:
            subnet_desc.free_address(addr=allocated_addr)

            raise docker_exceptions.ConnectToDockerNetError(
                f"failed to connect the container {d_node.inf_name()} to the network {self.__inf_name}"
            ) from err

        self.__connd_node_map[d_node.get_id()] = ConnectionInfo(
            subnet_label=subnet_label, addr=allocated_addr
        )

        d_node.push_connected_network(network=self)

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

        if node.state() != EntityState.DEPLOYED:
            self.__connd_node_map.pop(d_node.get_id())
            raise docker_exceptions.DisconnectFromDockerNetError(
                f"the node {d_node.inf_name()} with id {d_node.get_id()} is not deployed"
            )

        conn_info = self.__connd_node_map.get(d_node.get_id(), None)

        if conn_info is None:
            raise docker_exceptions.DisconnectFromDockerNetError(
                f"the node {d_node.inf_name()} with id {d_node.get_id()} is already disconnected"
            )

        container_id = d_node.docker_container_id()

        try:
            self.__dnet.disconnect(container=container_id)  # type: ignore
        except docker.errors.APIError as err:
            raise docker_exceptions.DisconnectFromDockerNetError(
                f"failed to disconnect the container {d_node.inf_name()} from the network {self.__inf_name}"
            ) from err

        self.__subnts_reg[conn_info.subnet_label].free_address(addr=conn_info.addr)  # type: ignore
        self.__connd_node_map.pop(d_node.get_id())

    def __get_node_connection_info(self, node: Node) -> ConnectionInfo:
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

        conn_info = self.__connd_node_map.get(node.get_id(), None)

        if conn_info is None:
            raise docker_exceptions.GetContainerIpError(
                f"the node {d_node.inf_name()} is not connected"
            )

        return conn_info

    # ------ приватные методы

    def __is_state_as_required(self, required: EntityState) -> bool:
        return self.__state == required
