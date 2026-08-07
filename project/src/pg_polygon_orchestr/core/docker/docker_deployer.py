from collections.abc import Mapping

from ..exception import docker_exceptions
from ..exception import common_exceptions
from ..configs import NodeConfig, VolumeConfig, NetConfig
from ..interfaces import Deployer, Node, Network, Volume

from . import docker_node, docker_volume, docker_network, docker_session


class DockerDeployer(Deployer):
    def __init__(self) -> None:
        self.__docker_nodes: dict[str, docker_node.DockerNode] = dict()
        self.__docker_networks: dict[str, docker_network.DockerNetwork] = dict()
        self.__docker_volumes: dict[str, docker_volume.DockerVolume] = dict()
        self.__docker_session: docker_session.DockerClientSession = (
            docker_session.DockerClientSession()
        )

    # ----- интерфейсные методы

    def put_node_config(self, name: str, config: NodeConfig) -> Node:
        search_result = self.__docker_nodes.get(name, None)

        if search_result is not None:
            return search_result

        d_node = docker_node.DockerNode(
            name=name, config=config, session=self.__docker_session
        )

        self.__docker_nodes[name] = d_node

        return d_node

    def put_network_config(self, name: str, config: NetConfig) -> Network:
        search_result = self.__docker_networks.get(name, None)

        if search_result is not None:
            return search_result

        d_net = docker_network.DockerNetwork(
            name=name, config=config, session=self.__docker_session
        )

        self.__docker_networks[name] = d_net

        return d_net

    def put_volume_config(self, name: str, config: VolumeConfig) -> Volume:
        search_result = self.__docker_volumes.get(name, None)

        if search_result is not None:
            return search_result

        d_volume = docker_volume.DockerVolume(
            name=name, config=config, session=self.__docker_session
        )

        self.__docker_volumes[name] = d_volume

        return d_volume

    def deploy_infrastructure(self) -> None:
        self.__deploy_volumes()

        self.__deploy_networks()

        self.__deploy_nodes()

    def clear_infrastructure(self) -> None:
        self.__clear_nodes()

        self.__clear_networks()

        self.__clear_volumes()

    def remove_infrastructure(self) -> None:
        self.__remove_nodes()

        self.__remove_networks()

        self.__remove_volumes()

        self.__docker_session.close()

    def get_nodes(self) -> Mapping[str, Node]:
        return self.__docker_nodes.copy()

    def get_network(self) -> Mapping[str, Network]:
        return self.__docker_networks.copy()

    def get_volumes(self) -> Mapping[str, Volume]:
        return self.__docker_volumes.copy()

    # ------ докер-специфичные функции

    def check_node_is_known(
        self, who_ask: docker_network.DockerNetwork, node: docker_node.DockerNode
    ) -> bool | None:
        net_name = who_ask.get_name()

        search_result = self.__docker_networks.get(net_name, None)

        if search_result is None or not (search_result is who_ask):
            return None

        node_search_result = self.__docker_nodes.get(node.get_name(), None)

        return node_search_result is not None and node_search_result is node

    # ------ приватные методы

    def __deploy_volumes(self) -> None:
        for volume_name in list(self.__docker_volumes.keys()):
            volume = self.__docker_volumes[volume_name]

            try:
                volume.deploy()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_volumes.pop(volume_name)
            except common_exceptions.EntityIsAlreadyDeployed:
                pass
            except docker_exceptions.DockerDeployError as err:
                raise docker_exceptions.DockerDeployError(
                    f"failed to deploy the volume {volume_name}"
                ) from err

    def __deploy_networks(self) -> None:
        for net_name in list(self.__docker_networks.keys()):
            network = self.__docker_networks[net_name]

            try:
                network.deploy()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_networks.pop(net_name)
            except common_exceptions.EntityIsAlreadyDeployed:
                pass
            except docker_exceptions.DockerDeployError as err:
                raise docker_exceptions.DockerDeployError(
                    f"failed to deploy the network {net_name}"
                ) from err

    def __deploy_nodes(self) -> None:
        for node_name in list(self.__docker_nodes.keys()):
            node = self.__docker_nodes[node_name]

            try:
                node.deploy()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_nodes.pop(node_name)
            except common_exceptions.EntityIsAlreadyDeployed:
                pass
            except docker_exceptions.DockerDeployError as err:
                raise docker_exceptions.DockerDeployError(
                    f"failed to deploy the node {node_name}"
                ) from err

    def __clear_nodes(self) -> None:
        for node_name in list(self.__docker_nodes.keys()):
            node = self.__docker_nodes[node_name]

            try:
                node.clear()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_nodes.pop(node_name)
            except common_exceptions.EntityIsNotDeployed:
                pass
            except docker_exceptions.DockerClearError as err:
                raise docker_exceptions.DockerClearError(
                    f"failed to clear the node {node_name}"
                ) from err

    def __clear_networks(self) -> None:
        for net_name in list(self.__docker_networks.keys()):
            network = self.__docker_networks[net_name]

            try:
                network.clear()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_networks.pop(net_name)
            except common_exceptions.EntityIsNotDeployed:
                pass
            except docker_exceptions.DockerClearError as err:
                raise docker_exceptions.DockerClearError(
                    f"failed to clear the network {net_name}"
                ) from err

    def __clear_volumes(self) -> None:
        for volume_name in list(self.__docker_volumes.keys()):
            volume = self.__docker_volumes[volume_name]

            try:
                volume.clear()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_volumes.pop(volume_name)
            except common_exceptions.EntityIsNotDeployed:
                pass
            except docker_exceptions.DockerClearError as err:
                raise docker_exceptions.DockerClearError(
                    f"failed to clear the volume {volume_name}"
                ) from err

    def __remove_nodes(self) -> None:
        for node_name in list(self.__docker_nodes.keys()):
            node = self.__docker_nodes[node_name]

            try:
                node.remove()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_nodes.pop(node_name)
            except docker_exceptions.DockerRemoveError as err:
                raise docker_exceptions.DockerRemoveError(
                    f"failed to remove the node {node_name}"
                ) from err

    def __remove_networks(self) -> None:
        for net_name in list(self.__docker_networks.keys()):
            network = self.__docker_networks[net_name]

            try:
                network.remove()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_networks.pop(net_name)
            except docker_exceptions.DockerRemoveError as err:
                raise docker_exceptions.DockerRemoveError(
                    f"failed to remove the network {net_name}"
                ) from err

    def __remove_volumes(self) -> None:
        for volume_name in list(self.__docker_volumes.keys()):
            volume = self.__docker_volumes[volume_name]

            try:
                volume.remove()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_volumes.pop(volume_name)
            except docker_exceptions.DockerRemoveError as err:
                raise docker_exceptions.DockerRemoveError(
                    f"failed to remove the volume {volume_name}"
                ) from err
