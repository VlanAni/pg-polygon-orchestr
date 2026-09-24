import tarfile
import os
import json
import typing
import inspect
import docker
import docker.errors

from ..common_types import SnapshotDescription, InfraType, EntityState
from ..exception import common_exceptions, docker_exceptions
from ..infra_configs import NetConfig, NodeConfig
from ..common_types import SubnetConfig
from ..mount import BindMountConfig
from ..infra import Deployer
from ..docker_infra import (
    DockerVolume,
    DockerNetwork,
    DockerNode,
    DockerDeployer,
    VolumeMountConfig,
)


class SnapshotInfraBuilder:
    """Класс, создающий инфраструктуру из snapshot'а"""

    def build(self, snapshot_desc: SnapshotDescription) -> Deployer:
        """_summary_

        Args:
            snapshot_desc (SnapshotDescription): дескриптор snapshot'а

        Raises:
            common_exceptions.FailedToFindSnapshotTar: не удаётся получить доступ к директории, содержащей архивы snapshot'ов в формате `.tar.gz`
            common_exceptions.FailedToBuildInfrastructure: не удаётся создать инфраструктуру из snapshot'а

        Returns:
            Deployer: конкретный деплоер, реализующий интерфейс `Deployer` (тип записит от типа инфраструктуры в `meta.json`)
        """
        sp = snapshot_desc.path

        if not (os.path.exists(sp)):
            raise common_exceptions.FailedToFindSnapshotTar(
                f"failed to find {snapshot_desc.path}"
            )

        with tarfile.open(name=sp, mode="r:gz") as snap_tar:
            try:
                meta_json = snap_tar.extractfile("meta.json")
            except KeyError as err:
                raise common_exceptions.FailedToBuildInfrastructure(
                    f"failed to find 'meta.json' file in {sp}"
                ) from err

            if meta_json is None:
                raise common_exceptions.FailedToBuildInfrastructure(
                    f"it seems that {sp} is incorrect"
                )

            try:
                meta_data = self.__parse_meta(meta_json)  # type: ignore
            except Exception as err:
                raise common_exceptions.FailedToBuildInfrastructure(
                    f"failed to parse 'meta.json' in {sp}"
                )
            finally:
                meta_json.close()

            if "type" in meta_data:
                type_name = typing.cast(str, meta_data["type"])
                if type_name == InfraType.DOCKER.name:
                    try:
                        return self.__build_docker_infra(
                            tarfile=snap_tar, meta_data=meta_data
                        )
                    except docker_exceptions.FailedToBuildDockerInsfrastructure as err:
                        raise common_exceptions.FailedToBuildInfrastructure(
                            f"failed to build a docker infrasturcture from {sp}"
                        ) from err
                else:
                    raise common_exceptions.FailedToBuildInfrastructure(
                        f"unknown infrastruction type - {type_name}"
                    )
            else:
                raise common_exceptions.FailedToBuildInfrastructure(
                    f"failed to extract an infrastruction type"
                )

    def __parse_meta(self, json_file_obj) -> dict[str, typing.Any]:  # type: ignore
        try:
            meta_data = typing.cast(dict[str, typing.Any], json.load(json_file_obj))  # type: ignore
        except Exception as err:
            raise Exception from err

        return meta_data

    def __build_docker_infra(
        self, tarfile: tarfile.TarFile, meta_data: dict[str, typing.Any]
    ) -> DockerDeployer:
        deployer = DockerDeployer()

        snapshot_files = {tarinfo.name: tarinfo for tarinfo in tarfile.getmembers()}
        snapshot_files_names = snapshot_files.keys()

        node_id_map: dict[str, DockerNode] = {}
        volume_id_map: dict[str, DockerVolume] = {}

        if "volumes" in meta_data:
            volume_id_list = typing.cast(list[str], meta_data["volumes"])
        else:
            raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                f"meta data does not have volumes data"
            )

        for vol_id in volume_id_list:
            if f"volumes/{vol_id}.json" in snapshot_files_names:
                try:
                    vol_info = tarfile.extractfile(
                        member=snapshot_files[f"volumes/{vol_id}.json"]
                    )

                    if vol_info is None:
                        raise Exception

                except Exception as err:
                    try:
                        deployer.destroy_infra()
                    except Exception:
                        raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                    raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                        f'failed to extract "volumes/{vol_id}.json"'
                    ) from err
            else:
                try:
                    deployer.destroy_infra()
                except Exception:
                    raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                    f'failed to find "volumes/{vol_id}.json"'
                )

            try:
                vol_data = typing.cast(dict[str, typing.Any], json.load(vol_info))
            except Exception as err:
                try:
                    deployer.destroy_infra()
                except Exception:
                    raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                    f'failed to parse "volumes/{vol_id}.json"'
                )
            finally:
                vol_info.close()

            try:
                volume = self.__build_docker_volume(
                    deployer=deployer, vol_data=vol_data
                )
            except docker_exceptions.FailedToBuildDockerVolume as err:
                try:
                    deployer.destroy_infra()
                except Exception:
                    raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                    f'failed to build the volume from "volumes/{vol_id}.json"'
                )

            volume_id_map[vol_id] = volume

        if "nodes" in meta_data:
            node_id_list = typing.cast(list[str], meta_data["nodes"])
        else:
            try:
                deployer.destroy_infra()
            except Exception:
                raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

            raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                f"failed to extract information about nodes"
            )

        for node_id in node_id_list:
            if f"nodes/{node_id}.json" in snapshot_files_names:
                try:
                    node_info = tarfile.extractfile(
                        member=snapshot_files[f"nodes/{node_id}.json"]
                    )

                    if node_info is None:
                        raise Exception

                except Exception as err:
                    try:
                        deployer.destroy_infra()
                    except Exception:
                        raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                    raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                        f'failed to extract "nodes/{node_id}.json"'
                    ) from err
            else:
                try:
                    deployer.destroy_infra()
                except Exception:
                    raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                    f'failed to find "nodes/{node_id}.json"'
                )

            try:
                node_data = typing.cast(dict[str, typing.Any], json.load(node_info))
            except Exception as err:
                try:
                    deployer.destroy_infra()
                except Exception:
                    raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                    f'failed to parse "nodes/{node_id}.json"'
                )
            finally:
                node_info.close()

            try:
                node = self.__build_docker_node(
                    deployer=deployer,
                    node_data=node_data,
                    id=node_id,
                    tarfile=tarfile,
                    volume_map=volume_id_map,
                )
            except docker_exceptions.FailedToBuildDockerNode as err:
                try:
                    deployer.destroy_infra()
                except Exception:
                    raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                    f'failed to build the volume from "nodes/{node_id}.json"'
                )

            node_id_map[node_id] = node

        if "networks" in meta_data:
            network_id_list = typing.cast(list[str], meta_data["networks"])
        else:
            try:
                deployer.destroy_infra()
            except Exception:
                raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

            raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                f"failed to extract information about nodes"
            )

        for net_id in network_id_list:
            if f"networks/{net_id}.json" in snapshot_files_names:
                try:
                    net_info = tarfile.extractfile(
                        member=snapshot_files[f"networks/{net_id}.json"]
                    )

                    if net_info is None:
                        raise Exception

                except Exception as err:
                    try:
                        deployer.destroy_infra()
                    except Exception:
                        raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                    raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                        f'failed to extract "networks/{net_id}.json"'
                    ) from err
            else:
                try:
                    deployer.destroy_infra()
                except Exception:
                    raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                    f'failed to find "networks/{net_id}.json"'
                )

            try:
                net_data = typing.cast(dict[str, typing.Any], json.load(net_info))
            except Exception as err:
                try:
                    deployer.destroy_infra()
                except Exception:
                    raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                    f'failed to parse "networks/{net_id}.json"'
                )
            finally:
                net_info.close()

            try:
                node = self.__build_docker_network(
                    deployer=deployer, net_data=net_data, node_id_map=node_id_map
                )
            except docker_exceptions.FailedToBuildDockerNetwork as err:
                try:
                    deployer.destroy_infra()
                except Exception:
                    raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                    f'failed to build the network from "networks/{net_id}.json"'
                )

        return deployer

    def __build_docker_volume(
        self, deployer: DockerDeployer, vol_data: dict[str, typing.Any]
    ) -> DockerVolume:
        if "name" in vol_data:
            name = vol_data["name"]
        else:
            raise docker_exceptions.FailedToBuildDockerVolume(
                f"failed to get the volume name"
            )

        if "state" in vol_data:
            state = vol_data["state"]

            if state not in [EntityState.DEPLOYED.name, EntityState.NOT_DEPLOYED.name]:
                raise docker_exceptions.FailedToBuildDockerVolume(
                    f"failed to recognise the state [{state}]"
                )
        else:
            raise docker_exceptions.FailedToBuildDockerVolume(f"failed to get a state")

        volume = deployer.add_docker_volume(name=name)

        if state == EntityState.DEPLOYED.name:
            try:
                volume.deploy()
            except Exception as err:
                raise docker_exceptions.FailedToBuildDockerVolume(
                    f"failed to deploy the volume {name}"
                ) from err

        return volume

    def __build_docker_node(
        self,
        deployer: DockerDeployer,
        node_data: dict[str, typing.Any],
        id: str,
        tarfile: tarfile.TarFile,
        volume_map: dict[str, DockerVolume],
    ) -> DockerNode:
        if "type" in node_data:
            if typing.cast(str, node_data["type"]) != InfraType.DOCKER.name:
                raise docker_exceptions.FailedToBuildDockerNode(
                    f"the node is not a docker node"
                )
        else:
            raise docker_exceptions.FailedToBuildDockerNode(
                f"failed to recognise the type"
            )

        if "name" in node_data:
            name = node_data["name"]
        else:
            raise docker_exceptions.FailedToBuildDockerNode(
                f"failed to get the volume name"
            )

        if "state" in node_data:
            state = node_data["state"]

            if state not in [EntityState.DEPLOYED.name, EntityState.NOT_DEPLOYED.name]:
                raise docker_exceptions.FailedToBuildDockerNode(
                    f"failed to recognise the state [{state}]"
                )
        else:
            raise docker_exceptions.FailedToBuildDockerNode(f"failed to get a state")

        if "config" in node_data:
            config_data = typing.cast(dict[str, typing.Any], node_data["config"])
        else:
            raise docker_exceptions.FailedToBuildDockerNode(f"failed to get a config")

        try:
            nc = NodeConfig.from_dict(data=config_data)
        except Exception:
            raise docker_exceptions.FailedToBuildDockerNode(
                f"failed to fetch correct config"
            )

        node = deployer.node_from_config(name=name, config=nc)
        node = typing.cast(DockerNode, node)

        if state == EntityState.DEPLOYED.name:
            image_tar_name = f"nodes/{id}.tar"

            try:
                image_tar_fo = tarfile.extractfile(member=image_tar_name)

                if image_tar_fo is None:
                    raise Exception
            except Exception:
                image_tar_fo = None

            if image_tar_fo is not None:
                try:
                    client = docker.from_env()
                except Exception as err:
                    image_tar_fo.close()
                    raise docker_exceptions.FailedToBuildDockerNode(
                        f"failed to open a docker-client session"
                    ) from err

                try:
                    loaded_image = client.images.load(data=image_tar_fo)[0]
                except docker.errors.APIError as err:
                    client.close()
                    raise docker_exceptions.FailedToBuildDockerNode(
                        f"failed to load the image from nodes/{id}.tar"
                    )
                finally:
                    image_tar_fo.close()

                try:
                    docker_tag_result = loaded_image.tag(repository=f"{str(node.uuid)}", tag="v0")  # type: ignore

                    if not (docker_tag_result):
                        raise Exception
                except Exception as err:
                    client.close()
                    raise docker_exceptions.FailedToBuildDockerNode(
                        f"failed to tag the image"
                    ) from err

                new_tag = f"{str(node.uuid)}:v0"

                try:
                    client.images.remove(image=f"snapshot_{id}:v0")  # type: ignore
                except Exception as err:
                    raise docker_exceptions.FailedToBuildDockerNode(
                        f"failed to delete old snapshot tag"
                    ) from err
                finally:
                    client.close()

                node._push_image_to_run(  # pyright: ignore[reportPrivateUsage]
                    image=loaded_image, image_tag=new_tag
                )

            bind_mount_configs: list[BindMountConfig] = []
            volume_mount_configs: list[VolumeMountConfig] = []

            if "bind_mount_configs" in node_data:
                for bmc_data in node_data["bind_mount_configs"]:

                    try:
                        bmc = BindMountConfig.from_dict(data=bmc_data)
                    except Exception as err:
                        raise docker_exceptions.FailedToBuildDockerNode(
                            f"failed to create a BindMountConfig"
                        ) from err

                    bind_mount_configs.append(bmc)

            else:
                raise docker_exceptions.FailedToBuildDockerNode(
                    f'JSON Encoded data does not include "bind_mount_configs"'
                )

            if "volume_mount_configs" in node_data:
                for vmc_data in node_data["volume_mount_configs"]:

                    try:
                        volume_id = vmc_data["volume"]
                    except Exception as err:
                        raise docker_exceptions.FailedToBuildDockerNode(
                            f"failed to get a Docker Volume UUID from JSON-Encoded data"
                        ) from err

                    volume = volume_map.get(volume_id)

                    if volume is None:
                        raise docker_exceptions.FailedToBuildDockerNode(
                            f"failed to find a Docker Volume with id {volume_id}"
                        )

                    vmc_signature = inspect.signature(
                        VolumeMountConfig
                    ).parameters.keys()
                    vmc_init_args: dict[str, typing.Any] = {"volume": volume}

                    for arg_name in vmc_signature:

                        if arg_name in vmc_init_args:
                            continue

                        try:
                            arg_value = vmc_data[arg_name]
                        except Exception as err:
                            raise docker_exceptions.FailedToBuildDockerNode(
                                f"failed to fetch {arg_name} value from JSON-Encoded data"
                            ) from err

                        vmc_init_args[arg_name] = arg_value

                    volume_mount_configs.append(VolumeMountConfig(**vmc_init_args))

            try:

                node.deploy(
                    bind_mount_configs=bind_mount_configs,
                    volume_mount_configs=volume_mount_configs,
                )

            except Exception as err:

                raise docker_exceptions.FailedToBuildDockerNode(
                    f"failed to deploy node {node.inf_name}"
                ) from err

        return node

    def __build_docker_network(
        self,
        deployer: DockerDeployer,
        node_id_map: dict[str, DockerNode],
        net_data: dict[str, typing.Any],
    ) -> None:
        if "type" in net_data:
            if typing.cast(str, net_data["type"]) != InfraType.DOCKER.name:
                raise docker_exceptions.FailedToBuildDockerNetwork(
                    f"the node is not a docker node"
                )
        else:
            raise docker_exceptions.FailedToBuildDockerNetwork(
                f"failed to recognise the type"
            )

        if "name" in net_data:
            name = net_data["name"]
        else:
            raise docker_exceptions.FailedToBuildDockerNetwork(
                f"failed to get the volume name"
            )

        if "state" in net_data:
            state = net_data["state"]

            if state not in [EntityState.DEPLOYED.name, EntityState.NOT_DEPLOYED.name]:
                raise docker_exceptions.FailedToBuildDockerNetwork(
                    f"failed to recognise the state [{state}]"
                )
        else:
            raise docker_exceptions.FailedToBuildDockerNetwork(f"failed to get a state")

        if "config" in net_data:
            config = typing.cast(dict[str, typing.Any], net_data["config"])
        else:
            raise docker_exceptions.FailedToBuildDockerNetwork(
                f"failed to get a config"
            )

        try:
            nc = NetConfig.from_dict(data=config)
        except Exception as err:
            raise docker_exceptions.FailedToBuildDockerNetwork(
                f"incorrect network config"
            ) from err

        net = deployer.network_from_config(name=name, config=nc)
        net = typing.cast(DockerNetwork, net)

        if state == EntityState.DEPLOYED.name:
            try:
                subnets_data = net_data["subnets_data"]

                subnet_configs: list[SubnetConfig] = []

                for label, ip_data in subnets_data.items():
                    config_values = ip_data
                    config_values["label"] = label

                    subnet_configs.append(
                        SubnetConfig(
                            **{
                                field: config_values[field]
                                for field in inspect.signature(
                                    SubnetConfig
                                ).parameters.keys()
                            },
                        )
                    )
            except:
                raise docker_exceptions.FailedToBuildDockerNetwork(
                    f"failed to get subnets configs"
                )

            try:
                net.deploy(subnet_configs=subnet_configs)
            except Exception as err:
                raise docker_exceptions.FailedToBuildDockerNetwork(
                    f"failed to deploy the network {net.inf_name}"
                ) from err

            try:
                conn_node_map = net_data["conn_node_map"]
            except Exception as err:
                raise docker_exceptions.FailedToBuildDockerNetwork(
                    f"failed to get 'connected_nodes' param"
                ) from err

            try:
                for node_id, conn_info in conn_node_map.items():
                    node = node_id_map[typing.cast(str, node_id)]

                    net.connect(
                        node=node,
                        **{field: conn_info[field] for field in conn_info.keys()},
                    )
            except Exception as err:
                raise docker_exceptions.FailedToBuildDockerNetwork(
                    f"failed to connect nodes to the network {net.inf_name}"
                )
