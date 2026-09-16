import ipaddress
import os
import pathlib
import tarfile
import uuid
import pytest
import docker

from pg_polygon_orchestr import DockerDeployer
from pg_polygon_orchestr import NodeConfig
from pg_polygon_orchestr import NetConfig
from pg_polygon_orchestr import VolumeConfig
from pg_polygon_orchestr import MountConfig
from pg_polygon_orchestr import SubnetConfig
from pg_polygon_orchestr import SnapshotInfraBuilder
from pg_polygon_orchestr import find_snap_desc
from pg_polygon_orchestr import HostPathDesc
from pg_polygon_orchestr import DockerNodeOptions

from .fixtures import check_exit_code
from .fixtures import deployer
from .fixtures import ipv4_subnet
from .fixtures import host_temp_dir

from .fixtures import CONTAINER_MOUNT_DIR

pytestmark = pytest.mark.integration


def _docker_daemon_available() -> bool:
    try:
        client = docker.from_env()
        client.ping()  # type: ignore
        client.close()
        return True
    except Exception:
        return False


skip_if_no_docker = pytest.mark.skipif(
    not _docker_daemon_available(),
    reason="can not access the docker daemon",
)


@skip_if_no_docker
class TestDockerSnapshot:

    def test_SNAPSHOT_1__snapshot_archive_exists(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        node_config = NodeConfig(os="alpine", cpu_limit=1, mem_limit="256m")

        net_config = NetConfig(internal=False)

        volume_config = VolumeConfig(docker_volume_driver="local")

        node = deployer.put_node_config("node_a", config=node_config)
        net = deployer.put_network_config("net", config=net_config)
        vol = deployer.put_volume_config("vol", config=volume_config)

        gateway = next(ipv4_subnet.hosts())

        net.deploy(
            subnet_configs=[
                SubnetConfig(label="1", subnet=ipv4_subnet, gateway=gateway)
            ]
        )
        vol.deploy()
        node.deploy(
            mount_configs=[
                MountConfig(
                    mounted=vol,
                    mount_path="/app/data",
                    read_only=False,
                )
            ]
        )

        node.start()

        net.connect(node=node, subnet_label=net.subnets()[0].label)

        deployer.make_snapshot()

        snapshot_dir = os.path.join(
            pathlib.Path.home(), ".pg-polygon-orchestr", "snapshots"
        )

        assert os.path.exists(path=snapshot_dir)

        assert os.path.exists(
            os.path.join(snapshot_dir, f"{str(deployer.uuid)}.tar.gz")
        )

        os.remove(path=os.path.join(snapshot_dir, f"{str(deployer.uuid)}.tar.gz"))

        deployer.make_snapshot(snapshot_name="my_test_snapshot", online=True)

        assert not os.path.exists(
            os.path.join(snapshot_dir, f"{str(deployer.uuid)}.tar.gz")
        )

        assert os.path.exists(os.path.join(snapshot_dir, "my_test_snapshot.tar.gz"))

        os.remove(path=os.path.join(snapshot_dir, "my_test_snapshot.tar.gz"))

    def test_SNAPSHOT_2__check_snapshot_archive_internals(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        node_config = NodeConfig(os="alpine", cpu_limit=1, mem_limit="256m")
        net_config = NetConfig(internal=False)
        volume_config = VolumeConfig(docker_volume_driver="local")

        snapshot_dir = os.path.join(
            pathlib.Path.home(), ".pg-polygon-orchestr", "snapshots"
        )

        node_a = deployer.put_node_config("node_a", config=node_config)
        node_b = deployer.put_node_config("node_b", config=node_config)
        node_c = deployer.put_node_config("node_c", config=node_config)
        net = deployer.put_network_config("net", config=net_config)
        vol = deployer.put_volume_config("vol", config=volume_config)

        a_id = node_a.uuid
        b_id = node_b.uuid
        c_id = node_c.uuid
        net_id = net.uuid
        vol_id = vol.uuid

        for n in [node_a, node_b, node_c]:
            n.deploy()
            n.start()

        net.deploy(
            subnet_configs=[
                SubnetConfig(
                    label="1", subnet=ipv4_subnet, gateway=next(ipv4_subnet.hosts())
                )
            ]
        )

        net.connect(node=node_a, subnet_label=net.subnets()[0].label)
        net.connect(node=node_c, subnet_label=net.subnets()[0].label)

        deployer.make_snapshot(snapshot_name="test_snapshot", online=True)

        tar_file_path = os.path.join(snapshot_dir, "test_snapshot.tar.gz")

        with tarfile.open(tar_file_path, "r:gz") as tar:
            names = tar.getnames()

            assert "meta.json" in names

            assert self.__check_node_data_in_snapshot_names(uuid=a_id, names=names)
            assert self.__check_node_data_in_snapshot_names(uuid=b_id, names=names)
            assert self.__check_node_data_in_snapshot_names(uuid=c_id, names=names)

            assert f"volumes/{str(vol_id)}.json" in names

            assert f"networks/{str(net_id)}.json" in names

            assert len(names) == 9

        os.remove(tar_file_path)

    def test_SNAPSHOT_3__build_infrastructire_from_snapshot(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        node_config = NodeConfig(os="alpine", cpu_limit=1, mem_limit="256m")
        net_config = NetConfig(internal=False)
        volume_config = VolumeConfig(docker_volume_driver="local")

        node_a = deployer.put_node_config("node_a", config=node_config)
        node_b = deployer.put_node_config("node_b", config=node_config)
        node_c = deployer.put_node_config("node_c", config=node_config)
        net = deployer.put_network_config("net", config=net_config)
        vol = deployer.put_volume_config("vol", config=volume_config)

        vol.deploy()

        mcfg = MountConfig(
            mounted=vol,
            mount_path="/app/data",
            read_only=False,
        )

        for node in [node_a, node_b, node_c]:
            node.deploy(mount_configs=[mcfg])
            node.start()

        net.deploy(
            subnet_configs=[
                SubnetConfig(
                    label="1", subnet=ipv4_subnet, gateway=next(ipv4_subnet.hosts())
                )
            ]
        )

        net.connect(node=node_a, subnet_label=net.subnets()[0].label)
        net.connect(node=node_b, subnet_label=net.subnets()[0].label)
        net.connect(node=node_c, subnet_label=net.subnets()[0].label)

        for node in [node_a, node_b, node_c]:
            pwd_res = node.exec(command="pwd")
            assert check_exit_code(exec_result=pwd_res, expected=0, equal=True)
            pwd = pwd_res.stdout.strip()  # type: ignore

            tres = node.exec(command=f"touch {pwd}/text.txt")
            assert check_exit_code(exec_result=tres, expected=0, equal=True)

            echo = node.exec(
                command=f"sh -c \"echo '{node.inf_name}' > {pwd}/text.txt\""
            )
            assert check_exit_code(exec_result=echo, expected=0, equal=True)

        snap_desc = deployer.make_snapshot(snapshot_name="my_snapshot", online=True)
        deployer.remove_infrastructure()

        loaded_deployer = SnapshotInfraBuilder().build(snapshot_desc=snap_desc)
        assert len(loaded_deployer.nodes.items()) == 3
        assert len(loaded_deployer.network.items()) == 1
        assert len(loaded_deployer.volumes.items()) == 1

        loaded_nodes = list(loaded_deployer.nodes.values())

        for i in range(len(loaded_nodes)):
            loaded_nodes[i].start()

        for i in range(len(loaded_nodes)):
            node = loaded_nodes[i]

            pwd_res = node.exec(command="pwd")
            assert check_exit_code(exec_result=pwd_res, expected=0, equal=True)
            pwd = pwd_res.stdout.strip()  # type: ignore

            cat = node.exec(command=f"cat {pwd}/text.txt")
            assert check_exit_code(exec_result=cat, expected=0, equal=True)
            assert f"{node.inf_name}" in cat.stdout  # type: ignore

            ping_1 = node.exec(
                command=f"ping -c 1 {loaded_nodes[(i + 1) % 3].real_name}"
            )
            ping_2 = node.exec(
                command=f"ping -c 1 {loaded_nodes[(i + 2) % 3].real_name}"
            )
            assert check_exit_code(exec_result=ping_1, expected=0, equal=True)
            assert check_exit_code(exec_result=ping_2, expected=0, equal=True)

        loaded_deployer.remove_infrastructure()

    def test_SNAPSHOT_4__snapshot_restore_preserves_host_mounted_directory_data(
        self, deployer: DockerDeployer, host_temp_dir: str
    ):
        node_config = NodeConfig(os="alpine", cpu_limit=1, mem_limit="256m")
        node = deployer.put_node_config(name="node_a", config=node_config)
        node.deploy(
            mount_configs=[
                MountConfig(
                    mounted=HostPathDesc(path=host_temp_dir),
                    mount_path=CONTAINER_MOUNT_DIR,
                    read_only=False,
                )
            ]
        )
        node.start()

        filename = "before_snapshot.txt"
        content = "data written before making a snapshot"

        write_result = node.exec(
            command=f"sh -c \"echo -n '{content}' > {CONTAINER_MOUNT_DIR}/{filename}\""
        )
        assert check_exit_code(exec_result=write_result, expected=0, equal=True)

        deployer.make_snapshot(snapshot_name="host_dir_snapshot", online=True)
        deployer.remove_infrastructure()

        host_file_path = os.path.join(host_temp_dir, filename)
        assert os.path.exists(host_file_path)
        with open(host_file_path, "r") as f:
            assert f.read() == content

        snapshot = find_snap_desc(target="host_dir_snapshot")
        assert snapshot

        loaded_infra = SnapshotInfraBuilder().build(snapshot_desc=snapshot)
        loaded_nodes = list(loaded_infra.nodes.values())
        assert len(loaded_nodes) == 1
        restored_node = loaded_nodes[0]

        restored_node.start()

        read_result = restored_node.exec(
            command=f'sh -c "cat {CONTAINER_MOUNT_DIR}/{filename}"'
        )
        assert check_exit_code(exec_result=read_result, expected=0, equal=True)
        assert content in read_result.stdout  # type: ignore

        new_filename = "after_restore.txt"
        new_content = "data written after restoring from snapshot"
        write_after_restore = restored_node.exec(
            command=f"sh -c \"echo -n '{new_content}' > {CONTAINER_MOUNT_DIR}/{new_filename}\""
        )
        assert check_exit_code(exec_result=write_after_restore, expected=0, equal=True)

        new_host_file_path = os.path.join(host_temp_dir, new_filename)
        assert os.path.exists(new_host_file_path)

        with open(new_host_file_path, "r") as f:
            assert f.read() == new_content

        loaded_infra.remove_infrastructure()

        snapshot_dir = os.path.join(
            pathlib.Path.home(), ".pg-polygon-orchestr", "snapshots"
        )
        tar_path = os.path.join(snapshot_dir, "host_dir_snapshot.tar.gz")
        if os.path.exists(tar_path):
            os.remove(tar_path)

    def test_SNAPSHOT_5__three_node_network_with_volumes_and_snapshot_of_dev_toolchain(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        light_node_config = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine",
            docker_params=DockerNodeOptions(detach_from_default_bridge=True),
        )
        database_config = NodeConfig(
            cpu_limit=4,
            mem_limit="8g",
            os="ubuntu:latest",
            docker_params=DockerNodeOptions(detach_from_default_bridge=True),
        )
        net_config = NetConfig(internal=False)

        node_a = deployer.put_node_config(name="node_a", config=light_node_config)
        node_b = deployer.put_node_config(name="node_b", config=light_node_config)
        database = deployer.put_node_config(name="database", config=database_config)

        net = deployer.put_network_config(name="net", config=net_config)

        volume = deployer.put_volume_config(
            name="volume_a", config=VolumeConfig(docker_volume_driver="local")
        )

        VOLUME_MOUNT_PATH = "/app/data"
        POSTGRES_SRC_MOUNT = "/usr/src/postgres"

        volume.deploy()
        net.deploy(
            subnet_configs=[
                SubnetConfig(
                    label="1", subnet=ipv4_subnet, gateway=next(ipv4_subnet.hosts())
                )
            ]
        )

        node_a.deploy(
            mount_configs=[
                MountConfig(
                    mounted=volume, mount_path=VOLUME_MOUNT_PATH, read_only=False
                )
            ]
        )
        node_b.deploy(
            mount_configs=[
                MountConfig(
                    mounted=volume, mount_path=VOLUME_MOUNT_PATH, read_only=False
                )
            ]
        )
        database.deploy(
            mount_configs=[
                MountConfig(
                    mounted=HostPathDesc(
                        path=os.path.join(pathlib.Path.home(), "postgres")
                    ),
                    mount_path=POSTGRES_SRC_MOUNT,
                    read_only=False,
                )
            ]
        )

        node_a.start()
        node_b.start()
        database.start()

        net.connect(node=node_a, subnet_label=net.subnets()[0].label)
        net.connect(node=node_b, subnet_label=net.subnets()[0].label)
        net.connect(node=database, subnet_label=net.subnets()[0].label)

        database.exec(
            command=f"sh -c 'apt-get update && apt-get install -y iputils-ping'"
        )

        a_ping_b = node_a.exec(f"ping -c 1 {node_b.real_name}")
        a_ping_db = node_a.exec(f"ping -c 1 {database.real_name}")
        b_ping_a = node_b.exec(f"ping -c 1 {node_a.real_name}")
        b_ping_db = node_b.exec(f"ping -c 1 {database.real_name}")
        db_ping_a = database.exec(f"ping -c 1 {node_a.real_name}")
        db_ping_b = database.exec(f"ping -c 1 {node_b.real_name}")

        assert check_exit_code(a_ping_b, 0, True)
        assert check_exit_code(a_ping_db, 0, True)
        assert check_exit_code(b_ping_a, 0, True)
        assert check_exit_code(b_ping_db, 0, True)
        assert check_exit_code(db_ping_a, 0, True)
        assert check_exit_code(db_ping_b, 0, True)

        write_a = node_a.exec(
            f"sh -c 'echo node_a_data > {VOLUME_MOUNT_PATH}/marker_{node_a.inf_name}.txt'"
        )
        write_b = node_b.exec(
            f"sh -c 'echo node_b_data > {VOLUME_MOUNT_PATH}/marker_{node_b.inf_name}.txt'"
        )
        assert check_exit_code(write_a, 0, True)
        assert check_exit_code(write_b, 0, True)

        read_a = node_a.exec(f"cat {VOLUME_MOUNT_PATH}/marker_{node_a.inf_name}.txt")
        read_b = node_b.exec(f"cat {VOLUME_MOUNT_PATH}/marker_{node_b.inf_name}.txt")
        assert check_exit_code(read_a, 0, True)
        assert check_exit_code(read_b, 0, True)
        assert "node_a_data" in read_a.stdout  # type: ignore
        assert "node_b_data" in read_b.stdout  # type: ignore

        update_result = database.exec("sh -c 'apt-get update -qq'")
        assert check_exit_code(update_result, 0, True)

        toolchain_install = database.exec("sh -c 'apt-get install -y -qq git gcc'")
        assert check_exit_code(toolchain_install, 0, True)

        gcc_check_before = database.exec("sh -c 'gcc --version'")
        assert check_exit_code(gcc_check_before, 0, True)

        repo_check_before = database.exec(
            f"sh -c 'test -f {POSTGRES_SRC_MOUNT}/postgresql/configure.ac'"
        )
        assert check_exit_code(repo_check_before, 0, True)

        snap_desc = deployer.make_snapshot(
            snapshot_name="pg_dev_infra_snapshot", online=True
        )
        deployer.remove_infrastructure()

        snapshot = find_snap_desc(target="pg_dev_infra_snapshot")
        assert snapshot

        loaded_deployer = SnapshotInfraBuilder().build(snapshot_desc=snap_desc)
        loaded_nodes_by_name = {
            node.inf_name: node for node in loaded_deployer.nodes.values()
        }
        assert set(loaded_nodes_by_name.keys()) == {"node_a", "node_b", "database"}

        restored_database = loaded_nodes_by_name["database"]
        restored_database.start()

        repo_check_after = restored_database.exec(
            f"sh -c 'test -f {POSTGRES_SRC_MOUNT}/postgresql/configure.ac'"
        )
        assert check_exit_code(repo_check_after, 0, True)

        gcc_check_after = restored_database.exec("sh -c 'gcc --version'")
        assert check_exit_code(gcc_check_after, 0, True)

        loaded_deployer.remove_infrastructure()

        snapshot_dir = os.path.join(
            pathlib.Path.home(), ".pg-polygon-orchestr", "snapshots"
        )
        tar_path = os.path.join(snapshot_dir, "pg_dev_infra_snapshot.tar.gz")
        if os.path.exists(tar_path):
            os.remove(tar_path)

    def __check_node_data_in_snapshot_names(
        self, uuid: uuid.UUID, names: list[str], check_fs_archive: bool = True
    ):
        return f"nodes/{str(uuid)}.json" in names and (
            (f"nodes/{str(uuid)}.tar" in names) if check_fs_archive else True
        )
