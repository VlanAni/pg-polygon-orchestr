import pytest
import tempfile
import os
import ipaddress
import random

from pg_polygon_orchestr import DockerDeployer
from pg_polygon_orchestr import ExecResult

CONTAINER_MOUNT_DIR = "/mnt/test_data"
CONTAINER_MOUNT_FILE = "/mnt/test_file.txt"

TEST_FILE_SIZE_MB = 8
SLOW_RATE_BYTES_PER_SEC = 1 * 1024 * 1024
FAST_RATE_BYTES_PER_SEC = 200 * 1024 * 1024
MIN_EXPECTED_SLOWDOWN = 2.0


@pytest.fixture
def deployer():
    deployer = DockerDeployer()
    yield deployer
    deployer.destroy_infra()


@pytest.fixture
def host_temp_dir():
    with tempfile.TemporaryDirectory(prefix="bind_mount_test_") as tmpdir:
        yield tmpdir


@pytest.fixture
def host_temp_file():
    fd, path = tempfile.mkstemp(prefix="bind_mount_test_", suffix=".txt")
    initial_content = "initial content from host\n"
    with os.fdopen(fd, "w") as f:
        f.write(initial_content)
    yield path, initial_content
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def nonexistent_host_path():
    with tempfile.TemporaryDirectory(prefix="bind_mount_test_parent_") as parent:
        missing_path = os.path.join(parent, "this_dir_does_not_exist")
        assert not os.path.exists(missing_path)
        yield missing_path


@pytest.fixture
def ipv4_subnet() -> ipaddress.IPv4Network:
    third_octet = random.randint(16, 32)
    return ipaddress.ip_network(f"10.{third_octet}.0.0/24")  # type: ignore


def generate_private_subnets(
    count: int = 5,
) -> list[ipaddress.IPv4Network]:
    if count < 1:
        raise ValueError(f"count must be positive")

    subnets: list[ipaddress.IPv4Network] = []

    mask = 24

    while len(subnets) < count:
        second_octet = random.randint(16, 31)
        third_octet = random.randint(0, 255)
        net = ipaddress.IPv4Network(
            f"10.{second_octet}.{third_octet}.0/{mask}", strict=False
        )
        if net not in subnets:
            subnets.append(net)

    return subnets


def check_exit_code(exec_result: ExecResult | None, expected: int, equal: bool) -> bool:
    if exec_result is None:
        return False

    if exec_result.exit_code is None:
        return False

    return (exec_result.exit_code == expected and equal) or (
        exec_result.exit_code != expected and (not equal)
    )
