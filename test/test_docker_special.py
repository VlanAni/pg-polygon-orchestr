import docker
import pytest
import subprocess

from pg_polygon_orchestr import NodeConfig
from pg_polygon_orchestr import DockerDeployer
from pg_polygon_orchestr import DockerNodeConfigOptions, DeviceRateLimit

from .fixtures import deployer
from .fixtures import check_exit_code

from .fixtures import FAST_RATE_BYTES_PER_SEC
from .fixtures import TEST_FILE_SIZE_MB
from .fixtures import SLOW_RATE_BYTES_PER_SEC
from .fixtures import MIN_EXPECTED_SLOWDOWN

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


def _docker_storage_device() -> str:

    result = subprocess.run(
        ["findmnt", "-no", "SOURCE", "--target", "/var/lib/docker"],
        capture_output=True,
        text=True,
    )
    raw_source = result.stdout.strip()
    device = raw_source.split("[")[0]

    if result.returncode != 0 or not device.startswith("/dev/"):
        pytest.skip("failed to get device path")

    parent = subprocess.run(
        ["lsblk", "-no", "pkname", device],
        capture_output=True,
        text=True,
    )
    parent_name = parent.stdout.strip()

    if parent.returncode == 0 and parent_name:
        device = f"/dev/{parent_name}"

    return device


@skip_if_no_docker
class TestDockerDeployerIntegration:

    def test_DISKIO_1__write_and_read_speed_respect_device_rate_limit(
        self,
        deployer: DockerDeployer,
    ):
        device_path = _docker_storage_device()

        slow_options = DockerNodeConfigOptions(
            device_write_bps=[DeviceRateLimit(device_path, SLOW_RATE_BYTES_PER_SEC)],
            device_read_bps=[DeviceRateLimit(device_path, SLOW_RATE_BYTES_PER_SEC)],
        )
        fast_options = DockerNodeConfigOptions(
            device_write_bps=[DeviceRateLimit(device_path, FAST_RATE_BYTES_PER_SEC)],
            device_read_bps=[DeviceRateLimit(device_path, FAST_RATE_BYTES_PER_SEC)],
        )

        slow_config = NodeConfig(
            os="alpine",
            cpu_limit=1,
            mem_limit="256m",
            docker_params=slow_options,
        )
        fast_config = NodeConfig(
            os="alpine",
            cpu_limit=1,
            mem_limit="256m",
            docker_params=fast_options,
        )

        slow_node = deployer.node_from_config(name="node_slow_disk", config=slow_config)
        fast_node = deployer.node_from_config(name="node_fast_disk", config=fast_config)

        slow_node.deploy()
        fast_node.deploy()

        slow_node.start()
        fast_node.start()

        for node in (slow_node, fast_node):
            probe = node.exec(
                "dd if=/dev/zero of=/tmp/o_direct_probe bs=4096 count=1 oflag=direct"
            )
            if probe is None or probe.exit_code != 0:
                pytest.skip(f"failed to write with o_direct mode: {probe.stderr}")  # type: ignore
            node.exec("rm -f /tmp/o_direct_probe")

        write_cmd = (
            f"dd if=/dev/zero of=/tmp/testfile bs=1M "
            f"count={TEST_FILE_SIZE_MB} oflag=direct"
        )

        slow_write = slow_node.exec(write_cmd)
        fast_write = fast_node.exec(write_cmd)

        assert slow_write is not None and slow_write.exit_code == 0
        assert fast_write is not None and fast_write.exit_code == 0

        read_cmd = "dd if=/tmp/testfile of=/dev/null bs=1M iflag=direct"

        slow_read = slow_node.exec(read_cmd)
        fast_read = fast_node.exec(read_cmd)

        assert slow_read is not None and slow_read.exit_code == 0
        assert fast_read is not None and fast_read.exit_code == 0

        assert slow_write.execution_time > fast_write.execution_time
        assert slow_read.execution_time > fast_read.execution_time

        assert (
            slow_write.execution_time
            > fast_write.execution_time * MIN_EXPECTED_SLOWDOWN
        )
        assert (
            slow_read.execution_time > fast_read.execution_time * MIN_EXPECTED_SLOWDOWN
        )

    def test_ENV_1_environment_variables_exists(self, deployer: DockerDeployer):
        env = {"SECRET": "my_secret", "MY_PORT": "5432", "DB": "POSTGRES"}

        config = NodeConfig(
            os="alpine",
            cpu_limit=1,
            mem_limit="512m",
            docker_params=DockerNodeConfigOptions(environment=env),
        )

        node = deployer.node_from_config(name="node", config=config)

        node.deploy()
        node.start()

        for var, value in env.items():
            echo_result = node.exec(command=f'sh -c "echo ${var}"')

            assert check_exit_code(exec_result=echo_result, expected=0, equal=True)

            assert value == echo_result.stdout.strip("\n")  # type: ignore
