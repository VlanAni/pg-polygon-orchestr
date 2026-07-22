"""
pytest -m integration test/integration/test_docker_integration.py -v
"""

import docker
import pytest

from pg_polygon_orchestr.core.configs.node_config import NodeConfig
from pg_polygon_orchestr.core.deployers.docker_deployer import DockerDeployer

pytestmark = pytest.mark.integration


def _docker_daemon_available() -> bool:
    try:
        client = docker.from_env()
        client.ping()
        client.close()
        return True
    except Exception:
        return False


skip_if_no_docker = pytest.mark.skipif(
    not _docker_daemon_available(),
    reason="can not access the docker daemon",
)


@pytest.fixture
def deployer():
    d = DockerDeployer()
    yield d
    d.destroy_everything()


@skip_if_no_docker
class TestDockerDeployerIntegration:
    def test_two_nodes_deployed_started_named_and_destroyed(self, deployer):
        config = NodeConfig(
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="alpine:latest",
        )

        node_a = deployer.deploy(config)
        node_b = deployer.deploy(config)

        node_a.start()
        node_b.start()

        client = docker.from_env()
        try:
            expected_names = {
                "docker_node_0_container",
                "docker_node_1_container",
            }

            containers = client.containers.list(all=True)
            our_containers = [c for c in containers if c.name in expected_names]

            assert len(our_containers) == 2, (
                f"expected 2 containers, found "
                f"{len(our_containers)}: {[c.name for c in our_containers]}"
            )

            actual_names = {c.name for c in our_containers}
            assert actual_names == expected_names
        finally:
            client.close()

        deployer.destroy_everything()

        client = docker.from_env()

        expected_container_names = {
            "docker_node_0_container",
            "docker_node_1_container",
        }

        containers = client.containers.list(all=True)
        our_containers = [c for c in containers if c.name in expected_container_names]

        assert len(our_containers) == 0
