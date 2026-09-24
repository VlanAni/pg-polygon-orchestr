import os
import pytest
import docker

from pg_polygon_orchestr import DockerDeployer
from pg_polygon_orchestr import NodeConfig
from pg_polygon_orchestr import BindMountConfig
from pg_polygon_orchestr import BindMount
from pg_polygon_orchestr import VolumeMountConfig
from pg_polygon_orchestr import DockerBindMountOpts

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
        node = deployer.node_from_config(name="node", config=node_config)

        volume = deployer.add_docker_volume(name="test_volume")

        volume.deploy()
        node.deploy(
            volume_mount_configs=[
                VolumeMountConfig(
                    volume=volume,
                    dst="/app/mounted_data",
                    ro=False,
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

    def test_MOUNT_2__read_only_volume(self, deployer: DockerDeployer):
        node_config = NodeConfig(cpu_limit=1, mem_limit="512m", os="ubuntu:latest")
        node = deployer.node_from_config(name="node", config=node_config)

        volume = deployer.add_docker_volume(name="test_volume")

        volume.deploy()
        node.deploy(
            volume_mount_configs=[
                VolumeMountConfig(
                    volume=volume,
                    dst="/app/mounted_data",
                    ro=True,
                )
            ]
        )

        node.start()

        result = node.exec("sh -c 'echo test > /app/mounted_data/file.txt'")
        assert check_exit_code(result, 0, False)

    def test_MOUNT_3__mount_directory_write_from_container_visible_on_host(
        self, deployer: DockerDeployer, host_temp_dir: str
    ):
        config = NodeConfig(os="alpine", cpu_limit=1, mem_limit="256m")
        node = deployer.node_from_config(name="test_node", config=config)

        filename = "from_container.txt"
        content = "written inside container"

        node.deploy(
            bind_mount_configs=[
                BindMountConfig(
                    host_mnt=BindMount(src=host_temp_dir),
                    dst=CONTAINER_MOUNT_DIR,
                    docker_mount_options=DockerBindMountOpts(ro=False),
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

        node = deployer.node_from_config(name="test_node", config=config)
        node.deploy(
            bind_mount_configs=[
                BindMountConfig(
                    host_mnt=BindMount(src=host_temp_dir),
                    dst=CONTAINER_MOUNT_DIR,
                    docker_mount_options=DockerBindMountOpts(ro=False),
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
        node = deployer.node_from_config(name="test_node", config=config)
        node.deploy(
            bind_mount_configs=[
                BindMountConfig(
                    host_mnt=BindMount(src=host_file_path),
                    dst=CONTAINER_MOUNT_FILE,
                    docker_mount_options=DockerBindMountOpts(ro=False),
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
        self, nonexistent_host_path: str
    ):
        with pytest.raises(KeyError):
            BindMount(src=nonexistent_host_path)

        assert not os.path.exists(nonexistent_host_path)

    def test_MOUNT_7__volume_shared_between_two_nodes(self, deployer: DockerDeployer):
        node_config = NodeConfig(cpu_limit=1, mem_limit="256m", os="alpine")

        node_a = deployer.node_from_config(name="node_a", config=node_config)
        node_b = deployer.node_from_config(name="node_b", config=node_config)

        volume = deployer.add_docker_volume(name="shared_volume")

        volume.deploy()

        vmc = VolumeMountConfig(
            volume=volume,
            dst="/shared",
            ro=False,
        )

        for node in [node_a, node_b]:
            node.deploy(volume_mount_configs=[vmc])
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
