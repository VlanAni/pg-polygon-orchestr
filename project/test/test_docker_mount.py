import os
import pytest
import docker

from pg_polygon_orchestr import DockerDeployer
from pg_polygon_orchestr import NodeConfig
from pg_polygon_orchestr import VolumeConfig
from pg_polygon_orchestr import HostPathDesc
from pg_polygon_orchestr import MountConfig
from pg_polygon_orchestr import docker_exceptions

from .fixtures import check_exit_code
from .fixtures import deployer
from .fixtures import host_temp_dir
from .fixtures import host_temp_file
from .fixtures import nonexistent_host_path

from .fixtures import CONTAINER_MOUNT_DIR
from .fixtures import CONTAINER_MOUNT_FILE

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
class TestDockerMount:

    def test_MOUNT_1__volume_mount_persistency(self, deployer: DockerDeployer):
        node_config = NodeConfig(cpu_limit=1, mem_limit="512m", os="ubuntu:latest")
        node = deployer.put_node_config(name="node", config=node_config)

        volume_conf = VolumeConfig(
            docker_volume_driver="local",
        )
        volume = deployer.put_volume_config(name="test_volume", config=volume_conf)

        volume.deploy()
        node.deploy(
            mount_configs=[
                MountConfig(
                    mounted=volume,
                    mount_path="/app/mounted_data",
                    read_only=False,
                )
            ]
        )

        node.start()

        result = node.exec("sh -c 'echo test > /app/mounted_data/file.txt'")
        assert check_exit_code(result, 0, True)

        node.stop(1)
        node.start()

        result = node.exec("cat /app/mounted_data/file.txt")
        assert check_exit_code(result, 0, True)
        assert "test" in result.stdout  # type: ignore

        node.stop(0)

        deployer.clear_infrastructure()

    def test_MOUNT_2__read_only_volume(self, deployer: DockerDeployer):
        node_config = NodeConfig(cpu_limit=1, mem_limit="512m", os="ubuntu:latest")
        node = deployer.put_node_config(name="node", config=node_config)

        volume_conf = VolumeConfig(docker_volume_driver="local")
        volume = deployer.put_volume_config(name="test_volume", config=volume_conf)

        volume.deploy()
        node.deploy(
            mount_configs=[
                MountConfig(
                    mounted=volume,
                    mount_path="/app/mounted_data",
                    read_only=True,
                )
            ]
        )

        node.start()

        result = node.exec("sh -c 'echo test > /app/mounted_data/file.txt'")
        assert check_exit_code(result, 0, False)

        node.stop(0)
        deployer.clear_infrastructure()
        deployer.remove_infrastructure()

    def test_MOUNT_3__mount_directory_write_from_container_visible_on_host(
        self, deployer: DockerDeployer, host_temp_dir: str
    ):
        config = NodeConfig(os="alpine", cpu_limit=1, mem_limit="256m")
        node = deployer.put_node_config(name="test_node", config=config)

        filename = "from_container.txt"
        content = "written inside container"

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

        result = node.exec(
            command=f"sh -c \"echo -n '{content}' > {CONTAINER_MOUNT_DIR}/{filename}\""
        )

        assert check_exit_code(exec_result=result, expected=0, equal=True)

        host_file_path = os.path.join(host_temp_dir, filename)
        assert os.path.exists(host_file_path)
        with open(host_file_path, "r") as f:
            actual_content = f.read()
        assert actual_content == content

    def test_MOUNT_4__mount_directory_write_from_host_visible_in_container(
        self, deployer: DockerDeployer, host_temp_dir: str
    ):
        filename = "from_host.txt"
        content = "written on host before container start"
        host_file_path = os.path.join(host_temp_dir, filename)

        with open(host_file_path, "w") as f:
            f.write(content)

        assert os.path.exists(host_file_path)
        with open(host_file_path, "r") as f:
            assert f.read() == content

        config = NodeConfig(os="alpine", cpu_limit=1, mem_limit="256m")

        node = deployer.put_node_config(name="test_node", config=config)
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

        result = node.exec(command=f'sh -c "cat {CONTAINER_MOUNT_DIR}/{filename}"')

        assert check_exit_code(exec_result=result, expected=0, equal=True)
        assert content in result.stdout  # type: ignore

    def test_MOUNT_5__mount_single_file(
        self, deployer: DockerDeployer, host_temp_file: tuple[str, str]
    ):
        host_file_path, expected_content = host_temp_file

        config = NodeConfig(os="alpine", cpu_limit=1, mem_limit="256m")
        node = deployer.put_node_config(name="test_node", config=config)
        node.deploy(
            mount_configs=[
                MountConfig(
                    mounted=HostPathDesc(path=host_file_path),
                    mount_path=CONTAINER_MOUNT_FILE,
                    read_only=False,
                )
            ]
        )
        node.start()

        result = node.exec(f'sh -c "cat {CONTAINER_MOUNT_FILE}"')

        assert check_exit_code(exec_result=result, expected=0, equal=True)
        assert expected_content == result.stdout  # type: ignore

        assert os.path.exists(host_file_path)
        with open(host_file_path, "r") as f:
            assert f.read() == expected_content

    def test_MOUNT_6__mount_nonexistent_directory_raises(
        self, deployer: DockerDeployer, nonexistent_host_path: str
    ):
        config = NodeConfig(os="alpine", cpu_limit=1, mem_limit="256m")
        node = deployer.put_node_config(name="test_node", config=config)
        with pytest.raises(docker_exceptions.DockerDeployError):
            node.deploy(
                mount_configs=[
                    MountConfig(
                        mounted=HostPathDesc(path=nonexistent_host_path),
                        mount_path=CONTAINER_MOUNT_DIR,
                        read_only=False,
                    )
                ]
            )

        assert not os.path.exists(nonexistent_host_path)

    def test_MOUNT_7__volume_shared_between_two_nodes(self, deployer: DockerDeployer):
        node_config = NodeConfig(cpu_limit=1, mem_limit="256m", os="alpine")

        node_a = deployer.put_node_config(name="node_a", config=node_config)
        node_b = deployer.put_node_config(name="node_b", config=node_config)

        volume_conf = VolumeConfig(docker_volume_driver="local")
        volume = deployer.put_volume_config(name="shared_volume", config=volume_conf)

        volume.deploy()

        mnt_config = MountConfig(
            mounted=volume,
            mount_path="/shared",
            read_only=False,
        )

        for node in [node_a, node_b]:
            node.deploy(mount_configs=[mnt_config])
            node.start()

        write_result = node_a.exec("sh -c 'echo from_node_a > /shared/shared.txt'")
        assert check_exit_code(write_result, 0, True)

        read_result = node_b.exec("cat /shared/shared.txt")
        assert check_exit_code(read_result, 0, True)
        assert "from_node_a" in read_result.stdout  # type: ignore

        write_back_result = node_b.exec(
            "sh -c 'echo from_node_b >> /shared/shared.txt'"
        )
        assert check_exit_code(write_back_result, 0, True)

        reread_result = node_a.exec("cat /shared/shared.txt")
        assert check_exit_code(reread_result, 0, True)
        assert "from_node_a" in reread_result.stdout  # type: ignore
        assert "from_node_b" in reread_result.stdout  # type: ignore

        node_a.stop(0)
        node_b.stop(0)
        deployer.clear_infrastructure()

    def test_MOUNT_8__volume_driver_opts_tmpfs_size_limit_enforced(
        self, deployer: DockerDeployer
    ):
        node_config = NodeConfig(cpu_limit=1, mem_limit="512m", os="alpine")
        node = deployer.put_node_config(name="node", config=node_config)

        volume_conf = VolumeConfig(
            docker_volume_driver="local",
            docker_driver_opts={
                "type": "tmpfs",
                "device": "tmpfs",
                "o": "size=1m",
            },
        )
        volume = deployer.put_volume_config(name="tmpfs_volume", config=volume_conf)
        volume.deploy()

        node.deploy(
            mount_configs=[
                MountConfig(
                    mounted=volume,
                    mount_path="/app/tmpfs_data",
                    read_only=False,
                )
            ]
        )
        node.start()

        small_write = node.exec(
            "sh -c 'dd if=/dev/zero of=/app/tmpfs_data/small.bin bs=1k count=100'"
        )
        assert check_exit_code(small_write, 0, True)

        oversized_write = node.exec(
            "sh -c 'dd if=/dev/zero of=/app/tmpfs_data/big.bin bs=1M count=5'"
        )
        assert check_exit_code(oversized_write, 0, False)

        node.stop(0)
        deployer.clear_infrastructure()
