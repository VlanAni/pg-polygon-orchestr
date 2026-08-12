from collections.abc import Mapping
import typing
import uuid
import concurrent.futures as pool
import os
import docker.errors as dockerapi_errors

from ..exception import docker_exceptions
from ..exception import common_exceptions
from ..configs import NodeConfig, VolumeConfig, NetConfig
from ..abstract import Deployer, Node, Network, Volume, EntityRegistry
from ..meta import Type
from ..snapshot import MakeSnapshotHelper
from .image_tar import save_image


from . import docker_node, docker_volume, docker_network, docker_session


class DockerDeployer(Deployer):
    def __init__(self, id: uuid.UUID | None = None) -> None:
        self.__uuid: uuid.UUID = uuid.uuid4() if id is None else id
        self.__docker_nodes: EntityRegistry = EntityRegistry()
        self.__docker_networks: EntityRegistry = EntityRegistry()
        self.__docker_volumes: EntityRegistry = EntityRegistry()
        self.__docker_session: docker_session.DockerClientSession = (
            docker_session.DockerClientSession()
        )

    # ----- интерфейсные методы

    def put_node_config(self, name: str, config: NodeConfig) -> Node:
        d_node = docker_node.DockerNode(
            name=name,
            config=config,
            session=self.__docker_session,
            shared_volume_registry=self.__docker_volumes,
        )

        if self.__docker_nodes.put_object_in_registry(deployer=self, entity=d_node):
            return d_node
        else:
            return typing.cast(
                docker_node.DockerNode,
                self.__docker_nodes.get_entity_by_name(d_node.get_name()),
            )

    def put_network_config(self, name: str, config: NetConfig) -> Network:
        d_net = docker_network.DockerNetwork(
            name=name,
            config=config,
            session=self.__docker_session,
            shared_node_registry=self.__docker_nodes,
        )

        if self.__docker_networks.put_object_in_registry(deployer=self, entity=d_net):
            return d_net
        else:
            return typing.cast(
                docker_network.DockerNetwork,
                self.__docker_networks.get_entity_by_name(d_net.get_name()),
            )

    def put_volume_config(self, name: str, config: VolumeConfig) -> Volume:
        d_volume = docker_volume.DockerVolume(
            name=name, config=config, session=self.__docker_session
        )

        if self.__docker_volumes.put_object_in_registry(deployer=self, entity=d_volume):
            return d_volume
        else:
            return typing.cast(
                docker_volume.DockerVolume,
                self.__docker_volumes.get_entity_by_name(d_volume.get_name()),
            )

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
        return typing.cast(Mapping[str, Node], self.__docker_nodes.get_name_map())

    def get_network(self) -> Mapping[str, Network]:
        return typing.cast(Mapping[str, Network], self.__docker_networks.get_name_map())

    def get_volumes(self) -> Mapping[str, Volume]:
        return typing.cast(Mapping[str, Volume], self.__docker_volumes.get_name_map())

    def get_id(self) -> uuid.UUID:
        return self.__uuid

    def transform_to_mapping(self) -> Mapping[str, typing.Any]:
        return {
            "type": Type.DOCKER,
            "uuid": self.__uuid,
            "nodes": list(self.__docker_nodes.get_uuid_map().keys()),
            "networks": list(self.__docker_networks.get_uuid_map().keys()),
            "volumes": list(self.__docker_volumes.get_uuid_map().keys()),
        }

    def make_snapshot(
        self,
        snapshot_name: str = "",
        online: bool = False,
        timeout_to_stop: int | None = None,
    ) -> None:
        with MakeSnapshotHelper(
            archive_name=snapshot_name if snapshot_name else self.__uuid
        ) as s:

            try:
                s.add_json_object_info(tag="meta.json", obj=self)
            except common_exceptions.MakeSnapshotError as err:
                s.destroy_tar()

                raise common_exceptions.MakeSnapshotError(
                    f"failed to serialize deployer's info"
                ) from err

            for network_uuid, network in self.__docker_networks.get_uuid_map().items():
                try:
                    s.add_json_object_info(
                        tag=f"networks/{str(network_uuid)}.json", obj=network
                    )
                except common_exceptions.MakeSnapshotError as err:
                    s.destroy_tar()

                    raise common_exceptions.MakeSnapshotError(
                        f"failed to serialize the volume {network.get_name()} with id {str(network_uuid)}"
                    ) from err

            stopped_nodes = []

            if not online:
                try:
                    stopped_nodes = self.__freeze_nodes_before_snapshot(
                        stop_timeout=timeout_to_stop if timeout_to_stop else 10
                    )
                except docker_exceptions.FailedToRestartNodesAfterFailedFreezing as err:
                    s.destroy_tar()

                    raise docker_exceptions.FailedToRestartContainersAfterFailedSnapshot(
                        f"failed to stop nodes and restart them"
                    ) from err
                except common_exceptions.MakeSnapshotError as err:
                    s.destroy_tar()

                    raise common_exceptions.MakeSnapshotError(
                        f"failed to make snapshot"
                    ) from err

            for volume_uuid, volume in self.__docker_volumes.get_uuid_map().items():
                try:
                    s.add_json_object_info(
                        tag=f"volumes/{str(volume_uuid)}.json", obj=volume
                    )
                except common_exceptions.MakeSnapshotError as err:
                    s.destroy_tar()

                    try:
                        self.__restart_stopped_nodes_after_snapshot(
                            stopped_nodes=stopped_nodes
                        )
                    except docker_exceptions.FailedToRestartContainers as err:
                        raise docker_exceptions.FailedToRestartContainersAfterFailedSnapshot(
                            f"failed to restart nodes after failed volume serializing"
                        ) from err

                    raise common_exceptions.MakeSnapshotError(
                        f"failed to serialize the volume {volume.get_name()} with id {str(volume_uuid)}"
                    ) from err

            for node_uuid, node in self.__docker_nodes.get_uuid_map().items():
                try:
                    s.add_json_object_info(tag=f"nodes/{str(node_uuid)}.json", obj=node)
                except common_exceptions.MakeSnapshotError as err:
                    s.destroy_tar()

                    raise common_exceptions.MakeSnapshotError(
                        f"failed to serialize the node {node.get_name()} with id {str(node_uuid)}"
                    ) from err

                d_node = typing.cast(docker_node.DockerNode, node)

                try:
                    image = d_node.docker_commit(pause=True)
                except common_exceptions.EntityIsRemovedException:
                    self.__docker_nodes.pop_object_from_registry(
                        deployer=self, entity=node
                    )
                    continue
                except common_exceptions.EntityIsNotDeployed:
                    continue
                except docker_exceptions.ContainerDoesNotExist:
                    continue
                except docker_exceptions.FailedToCommit as err:
                    s.destroy_tar()

                    try:
                        self.__restart_stopped_nodes_after_snapshot(
                            stopped_nodes=stopped_nodes
                        )
                    except docker_exceptions.FailedToRestartContainers as err:
                        raise docker_exceptions.FailedToRestartContainersAfterFailedSnapshot(
                            f"failed to restart nodes after failed commit"
                        ) from err

                    raise common_exceptions.MakeSnapshotError(
                        f"failed to commit the container {d_node.get_name()}"
                    )

                try:
                    itd = save_image(
                        image=image,
                        dir=s.get_snapshot_dir_path(),
                        tar_name=str(node_uuid),
                    )
                except docker_exceptions.FailedToSaveImageIntoTar as err:
                    s.destroy_tar()

                    try:
                        self.__restart_stopped_nodes_after_snapshot(
                            stopped_nodes=stopped_nodes
                        )
                    except docker_exceptions.FailedToRestartContainers as err:
                        raise docker_exceptions.FailedToRestartContainersAfterFailedSnapshot(
                            f"failed to restart nodes after failed save"
                        ) from err

                    raise common_exceptions.MakeSnapshotError(
                        f"failed to save the image {image}"
                    ) from err

                try:
                    image.remove()
                except dockerapi_errors.APIError as err:
                    s.destroy_tar()
                    os.remove(itd.get_path())
                    try:
                        self.__restart_stopped_nodes_after_snapshot(
                            stopped_nodes=stopped_nodes
                        )
                    except docker_exceptions.FailedToRestartContainers as err:
                        raise docker_exceptions.FailedToRestartContainersAfterFailedSnapshot(
                            f"failed to restart nodes after deleting the image {image}"
                        ) from err

                    raise common_exceptions.MakeSnapshotError(
                        f"failed to delete the image {image}"
                    ) from err

                try:
                    s.put_tar_file_into_snapshot(
                        tag=f"nodes/{str(node_uuid)}.tar",
                        path=itd.get_path(),
                        size=itd.get_size(),
                    )
                except common_exceptions.MakeSnapshotError as err:
                    s.destroy_tar()
                    os.remove(itd.get_path())
                    try:
                        self.__restart_stopped_nodes_after_snapshot(
                            stopped_nodes=stopped_nodes
                        )
                    except docker_exceptions.FailedToRestartContainers as err:
                        raise docker_exceptions.FailedToRestartContainersAfterFailedSnapshot(
                            f"failed to restart nodes after failed 'put tar into snapshot'"
                        ) from err

                    raise common_exceptions.MakeSnapshotError(
                        f"failed to put the .tar of the image {image}"
                    ) from err

                os.remove(path=itd.get_path())

            if not online:
                try:
                    self.__restart_stopped_nodes_after_snapshot(
                        stopped_nodes=stopped_nodes
                    )
                except docker_exceptions.FailedToRestartContainers as err:
                    raise docker_exceptions.FailedToRestartContainersAfterSuccessSnapshot(
                        f"failed to restart all stopped nodes after making snapshot"
                    ) from err

    # ------ приватные методы

    def __deploy_volumes(self) -> None:
        for volume_name in list(self.__docker_volumes.get_name_map().keys()):
            volume = self.__docker_volumes.get_entity_by_name(name=volume_name)
            volume = typing.cast(docker_volume.DockerVolume, volume)

            try:
                volume.deploy()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_volumes.pop_object_from_registry(
                    deployer=self, entity=volume
                )
            except common_exceptions.EntityIsAlreadyDeployed:
                pass
            except docker_exceptions.DockerDeployError as err:
                raise docker_exceptions.DockerDeployError(
                    f"failed to deploy the volume {volume_name}"
                ) from err

    def __deploy_networks(self) -> None:
        for net_name in list(self.__docker_networks.get_name_map().keys()):
            network = self.__docker_networks.get_entity_by_name(name=net_name)
            network = typing.cast(docker_network.DockerNetwork, network)

            try:
                network.deploy()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_networks.pop_object_from_registry(
                    deployer=self, entity=network
                )
            except common_exceptions.EntityIsAlreadyDeployed:
                pass
            except docker_exceptions.DockerDeployError as err:
                raise docker_exceptions.DockerDeployError(
                    f"failed to deploy the network {net_name}"
                ) from err

    def __deploy_nodes(self) -> None:
        for node_name in list(self.__docker_nodes.get_name_map().keys()):
            node = self.__docker_nodes.get_entity_by_name(name=node_name)
            node = typing.cast(docker_node.DockerNode, node)

            try:
                node.deploy()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_nodes.pop_object_from_registry(deployer=self, entity=node)
            except common_exceptions.EntityIsAlreadyDeployed:
                pass
            except docker_exceptions.DockerDeployError as err:
                raise docker_exceptions.DockerDeployError(
                    f"failed to deploy the node {node_name}"
                ) from err

    def __clear_nodes(self) -> None:
        for node_name in list(self.__docker_nodes.get_name_map().keys()):
            node = self.__docker_nodes.get_entity_by_name(name=node_name)
            node = typing.cast(docker_node.DockerNode, node)

            try:
                node.clear()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_nodes.pop_object_from_registry(deployer=self, entity=node)
            except common_exceptions.EntityIsNotDeployed:
                pass
            except docker_exceptions.DockerClearError as err:
                raise docker_exceptions.DockerClearError(
                    f"failed to clear the node {node_name}"
                ) from err

    def __clear_networks(self) -> None:
        for net_name in list(self.__docker_networks.get_name_map().keys()):
            network = self.__docker_networks.get_entity_by_name(name=net_name)
            network = typing.cast(docker_network.DockerNetwork, network)

            try:
                network.clear()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_networks.pop_object_from_registry(
                    deployer=self, entity=network
                )
            except common_exceptions.EntityIsNotDeployed:
                pass
            except docker_exceptions.DockerClearError as err:
                raise docker_exceptions.DockerClearError(
                    f"failed to clear the network {net_name}"
                ) from err

    def __clear_volumes(self) -> None:
        for volume_name in list(self.__docker_volumes.get_name_map().keys()):
            volume = self.__docker_volumes.get_entity_by_name(name=volume_name)
            volume = typing.cast(docker_volume.DockerVolume, volume)

            try:
                volume.clear()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_volumes.pop_object_from_registry(
                    deployer=self, entity=volume
                )
            except common_exceptions.EntityIsNotDeployed:
                pass
            except docker_exceptions.DockerClearError as err:
                raise docker_exceptions.DockerClearError(
                    f"failed to clear the volume {volume_name}"
                ) from err

    def __remove_nodes(self) -> None:
        for node_name in list(self.__docker_nodes.get_name_map().keys()):
            node = self.__docker_nodes.get_entity_by_name(name=node_name)
            node = typing.cast(docker_node.DockerNode, node)

            try:
                node.remove()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_nodes.pop_object_from_registry(deployer=self, entity=node)
            except docker_exceptions.DockerRemoveError as err:
                raise docker_exceptions.DockerRemoveError(
                    f"failed to remove the node {node_name}"
                ) from err

    def __remove_networks(self) -> None:
        for net_name in list(self.__docker_networks.get_name_map().keys()):
            network = self.__docker_networks.get_entity_by_name(name=net_name)
            network = typing.cast(docker_network.DockerNetwork, network)

            try:
                network.remove()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_networks.pop_object_from_registry(
                    deployer=self, entity=network
                )
            except docker_exceptions.DockerRemoveError as err:
                raise docker_exceptions.DockerRemoveError(
                    f"failed to remove the network {net_name}"
                ) from err

    def __remove_volumes(self) -> None:
        for volume_name in list(self.__docker_volumes.get_name_map().keys()):
            volume = self.__docker_volumes.get_entity_by_name(name=volume_name)
            volume = typing.cast(docker_volume.DockerVolume, volume)

            try:
                volume.remove()
            except common_exceptions.EntityIsRemovedException:
                self.__docker_volumes.pop_object_from_registry(
                    deployer=self, entity=volume
                )
            except docker_exceptions.DockerRemoveError as err:
                raise docker_exceptions.DockerRemoveError(
                    f"failed to remove the volume {volume_name}"
                ) from err

    def __freeze_nodes_before_snapshot(
        self, stop_timeout: int
    ) -> list[docker_node.DockerNode]:
        nodes_registry_size = len(self.__docker_nodes.get_uuid_map())
        stopped_nodes: list[docker_node.DockerNode] = list()

        with pool.ThreadPoolExecutor(max_workers=nodes_registry_size) as executor:
            future_to_nodes: dict[pool.Future[None], docker_node.DockerNode] = {}
            for node_uuid in self.__docker_nodes.get_uuid_map().keys():
                node = typing.cast(
                    typ=docker_node.DockerNode,
                    val=self.__docker_nodes.get_entity_by_id(uuid=node_uuid),
                )

                future_to_nodes[executor.submit(node.stop, stop_timeout)] = node

            error_flag: Exception | None = None

            for f in pool.as_completed(future_to_nodes):
                node = future_to_nodes[f]
                try:
                    f.result()
                    stopped_nodes.append(node)
                except common_exceptions.EntityIsNotDeployed:
                    pass
                except common_exceptions.EntityIsRemovedException:
                    self.__docker_nodes.pop_object_from_registry(
                        deployer=self, entity=node
                    )
                except docker_exceptions.ContainerDoesNotExist:
                    pass
                except docker_exceptions.ContainerAlreadyStopped:
                    pass
                except docker_exceptions.DockerContStopError as err:
                    error_flag = err

        if error_flag:
            for node in stopped_nodes:
                try:
                    node.start()
                except docker_exceptions.DockerContStartError as err:
                    raise docker_exceptions.FailedToRestartNodesAfterFailedFreezing(
                        f"failed to restart the node {node.get_name()}"
                    ) from err

            raise common_exceptions.MakeSnapshotError(
                f"failed to freeze infrastructure. Tried to restart stopped nodes"
            ) from error_flag

        return stopped_nodes

    def __restart_stopped_nodes_after_snapshot(
        self, stopped_nodes: list[docker_node.DockerNode]
    ) -> None:
        with pool.ThreadPoolExecutor(max_workers=len(stopped_nodes)) as executor:
            future_to_nodes: dict[pool.Future[None], docker_node.DockerNode] = {
                executor.submit(node.start): node for node in stopped_nodes
            }

            error_flag: Exception | None = None

            for f in pool.as_completed(future_to_nodes):
                try:
                    f.result()
                except common_exceptions.EntityIsNotDeployed:
                    pass
                except common_exceptions.EntityIsRemovedException:
                    self.__docker_nodes.pop_object_from_registry(
                        deployer=self, entity=future_to_nodes[f]
                    )
                except docker_exceptions.ContainerAlreadyRunning:
                    pass
                except docker_exceptions.DockerContStartError as err:
                    error_flag = err

            if error_flag:
                raise docker_exceptions.FailedToRestartContainers(
                    f"failed to restart all nodes"
                ) from error_flag
