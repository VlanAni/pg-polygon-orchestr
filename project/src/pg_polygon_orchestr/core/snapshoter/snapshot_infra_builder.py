import tarfile
import os
import json
import typing
import docker
import docker.errors

from ..meta import (
    SnapshotDescription,
    Type,
    EntityState,
    MountConfig,
    MountableType,
    HostPathDesc,
)
from ..abstract import Deployer
from ..exception import common_exceptions, docker_exceptions
from ..docker import DockerDeployer, docker_node, docker_volume, docker_network
from ..configs import VolumeConfig, NetConfig, NodeConfig


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
                if type_name == Type.DOCKER.name:
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

        node_id_map: dict[str, docker_node.DockerNode] = {}
        volume_id_map: dict[str, docker_volume.DockerVolume] = {}

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
                        deployer.remove_infrastructure()
                    except Exception:
                        raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                    raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                        f'failed to extract "volumes/{vol_id}.json"'
                    ) from err
            else:
                try:
                    deployer.remove_infrastructure()
                except Exception:
                    raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                    f'failed to find "volumes/{vol_id}.json"'
                )

            try:
                vol_data = typing.cast(dict[str, typing.Any], json.load(vol_info))
            except Exception as err:
                try:
                    deployer.remove_infrastructure()
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
                    deployer.remove_infrastructure()
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
                deployer.remove_infrastructure()
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
                        deployer.remove_infrastructure()
                    except Exception:
                        raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                    raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                        f'failed to extract "nodes/{node_id}.json"'
                    ) from err
            else:
                try:
                    deployer.remove_infrastructure()
                except Exception:
                    raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                    f'failed to find "nodes/{node_id}.json"'
                )

            try:
                node_data = typing.cast(dict[str, typing.Any], json.load(node_info))
            except Exception as err:
                try:
                    deployer.remove_infrastructure()
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
                    deployer.remove_infrastructure()
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
                deployer.remove_infrastructure()
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
                        deployer.remove_infrastructure()
                    except Exception:
                        raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                    raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                        f'failed to extract "networks/{net_id}.json"'
                    ) from err
            else:
                try:
                    deployer.remove_infrastructure()
                except Exception:
                    raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                    f'failed to find "networks/{net_id}.json"'
                )

            try:
                net_data = typing.cast(dict[str, typing.Any], json.load(net_info))
            except Exception as err:
                try:
                    deployer.remove_infrastructure()
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
                    deployer.remove_infrastructure()
                except Exception:
                    raise docker_exceptions.FailedToRemoveInfrastructureAfterFailedBuild

                raise docker_exceptions.FailedToBuildDockerInsfrastructure(
                    f'failed to build the volume from "networks/{net_id}.json"'
                )

        return deployer

    def __build_docker_volume(
        self, deployer: DockerDeployer, vol_data: dict[str, typing.Any]
    ) -> docker_volume.DockerVolume:
        if "type" in vol_data:
            if typing.cast(str, vol_data["type"]) != Type.DOCKER.name:
                raise docker_exceptions.FailedToBuildDockerVolume(
                    f"the volume is not a docker volume"
                )
        else:
            raise docker_exceptions.FailedToBuildDockerVolume(
                f"failed to recognise the type"
            )

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

        if "config" in vol_data:
            config = typing.cast(dict[str, typing.Any], vol_data["config"])
        else:
            raise docker_exceptions.FailedToBuildDockerVolume(f"failed to get a config")

        try:
            vc = VolumeConfig(
                docker_driver_opts=config["docker_driver_opts"],
                docker_volume_driver=config["docker_volume_driver"],
            )
        except Exception as err:
            raise docker_exceptions.FailedToBuildDockerVolume(
                f"incorrect config for the volume"
            )

        volume = deployer.put_volume_config(name=name, config=vc)

        if state == EntityState.DEPLOYED.name:
            try:
                volume.deploy()
            except Exception as err:
                raise docker_exceptions.FailedToBuildDockerVolume(
                    f"failed to deploy the volume {name}"
                ) from err

        return typing.cast(docker_volume.DockerVolume, volume)

    def __build_docker_node(
        self,
        deployer: DockerDeployer,
        node_data: dict[str, typing.Any],
        id: str,
        tarfile: tarfile.TarFile,
        volume_map: dict[str, docker_volume.DockerVolume],
    ) -> docker_node.DockerNode:
        if "type" in node_data:
            if typing.cast(str, node_data["type"]) != Type.DOCKER.name:
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
            config = typing.cast(dict[str, typing.Any], node_data["config"])
        else:
            raise docker_exceptions.FailedToBuildDockerNode(f"failed to get a config")

        nc = NodeConfig(
            os=config["os"],
            cpu_limit=config["cpu_limit"],
            mem_limit=config["mem_limit"],
            ip_forwarding=config["ip_forwarding"],
            net_settings_roots=config["net_settings_roots"],
            storage_limit=config["storage_limit"],
            connect_to_docker_default=config["connect_to_docker_default"],
        )

        node = deployer.put_node_config(name=name, config=nc)
        node = typing.cast(docker_node.DockerNode, node)

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
                    docker_tag_result = loaded_image.tag(repository=f"{str(node.get_id())}", tag="v0")  # type: ignore

                    if not (docker_tag_result):
                        raise Exception
                except Exception as err:
                    client.close()
                    raise docker_exceptions.FailedToBuildDockerNode(
                        f"failed to tag the image"
                    ) from err

                new_tag = f"{str(node.get_id())}:v0"

                try:
                    client.images.remove(image=f"snapshot_{id}:v0")  # type: ignore
                except Exception as err:
                    raise docker_exceptions.FailedToBuildDockerNode(
                        f"failed to delete old snapshot tag"
                    ) from err
                finally:
                    client.close()

                node.push_image_to_run(image=loaded_image, image_tag=new_tag)

            mount_configs: list[MountConfig] = []

            if "mounted" in node_data:
                for mnt_src in node_data["mounted"].keys():
                    try:
                        mtype_name = node_data["mounted"][mnt_src]["mounted"]["type"]
                        if mtype_name == MountableType.VOLUME.name:
                            mounted = volume_map.get(mnt_src, None)

                            if mounted is None:
                                raise docker_exceptions.FailedToBuildDockerNode(
                                    f"cannot find a docker volume"
                                )
                        elif mtype_name == MountableType.HOSTPATH.name:
                            if not os.path.exists(mnt_src):
                                raise docker_exceptions.FailedToBuildDockerNode(
                                    f"cannot find the path {mnt_src} on the host"
                                )

                            mounted = HostPathDesc(path=mnt_src)
                    except Exception as err:
                        raise docker_exceptions.FailedToBuildDockerNode(
                            f"cannot find the path {mnt_src} on the host"
                        )

                    try:
                        mount_configs.append(
                            MountConfig(
                                mounted=mounted,  # type: ignore
                                mount_path=node_data["mounted"][mnt_src]["mount_path"],
                                read_only=node_data["mounted"][mnt_src]["read_only"],
                            )
                        )
                    except Exception as err:
                        raise docker_exceptions.FailedToBuildDockerNode(
                            f"failed to extract mount config for the volume {mnt_src}"
                        ) from err
            else:
                raise docker_exceptions.FailedToBuildDockerNode(
                    f'cannot extract "mounted" field'
                )

            try:
                node.deploy(mount_configs=mount_configs)
            except Exception as err:
                raise docker_exceptions.FailedToBuildDockerNode(
                    f"failed to deploy node {node.inf_name()}"
                ) from err

        return node

    def __build_docker_network(
        self,
        deployer: DockerDeployer,
        node_id_map: dict[str, docker_node.DockerNode],
        net_data: dict[str, typing.Any],
    ) -> None:
        if "type" in net_data:
            if typing.cast(str, net_data["type"]) != Type.DOCKER.name:
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
            nc = NetConfig(
                internal=config["internal"],
                ipv4=config["ipv4"],
                ipv6=config["ipv6"],
                docker_net_driver=config["docker_net_driver"],
            )
        except Exception as err:
            raise docker_exceptions.FailedToBuildDockerNetwork(
                f"incorrect network config"
            ) from err

        net = deployer.put_network_config(name=name, config=nc)
        net = typing.cast(docker_network.DockerNetwork, net)

        if state == EntityState.DEPLOYED.name:
            try:
                subnet = net_data["network-ip"]
                gateway = net_data["gateway-ip"]
            except:
                raise docker_exceptions.FailedToBuildDockerNetwork(
                    f"failed to get subnet and gateway ip addresses"
                )

            try:
                net.deploy(ip=subnet, gateway=gateway)
            except Exception as err:
                raise docker_exceptions.FailedToBuildDockerNetwork(
                    f"failed to deploy the network {net.inf_name()}"
                ) from err

            try:
                connected_nodes = net_data["connected_nodes"]
            except Exception as err:
                raise docker_exceptions.FailedToBuildDockerNetwork(
                    f"failed to get 'connected_nodes' param"
                ) from err

            try:
                for node_id, ip_addr in connected_nodes.items():
                    node = node_id_map[typing.cast(str, node_id)]

                    ipv4 = ip_addr["ipv4"] if nc.ipv4 else ""
                    ipv6 = ip_addr["ipv6"] if nc.ipv6 else ""

                    net.connect_node(node=node, ipv4_addr=ipv4, ipv6_addr=ipv6)
            except Exception as err:
                raise docker_exceptions.FailedToBuildDockerNetwork(
                    f"failed to connect nodes to the network {net.inf_name()}"
                )
