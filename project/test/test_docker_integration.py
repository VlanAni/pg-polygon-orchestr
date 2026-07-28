"""
pytest -m integration test/integration/test_docker_integration.py -v
"""

import docker
import pytest

from pg_polygon_orchestr.core.configs.node_config import NodeConfig
from pg_polygon_orchestr.core.configs.infra_config import InfConfig
from pg_polygon_orchestr.core.deployers.docker_deployer import DockerDeployer

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


@pytest.fixture
def deployer():
    d = DockerDeployer()
    yield d
    d.destroy_everything()


@skip_if_no_docker
class TestDockerDeployerIntegration:
    def test_two_nodes_deployed_started_named_and_destroyed(
        self, deployer: DockerDeployer
    ):
        config = NodeConfig(
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="alpine:latest",
        )

        node_a = deployer.deploy_node(config)  # type: ignore
        node_b = deployer.deploy_node(config)  # type: ignore

        node_a.start()  # pyright: ignore[reportUnknownMemberType]
        node_b.start()  # type: ignore

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

        deployer.destroy_everything()  # type: ignore

        client = docker.from_env()

        expected_container_names = {
            "docker_node_0_container",
            "docker_node_1_container",
        }

        containers = client.containers.list(all=True)
        our_containers = [c for c in containers if c.name in expected_container_names]

        client.close()

        assert len(our_containers) == 0

        assert len(deployer.get_images()) == 0  # type: ignore

        assert len(deployer.get_nodes()) == 0  # type: ignore

    def test_infrastructure_four_nodes_start_stop_destroy(
        self, deployer: DockerDeployer
    ):
        config1 = NodeConfig(
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="alpine:latest",
        )

        config2 = NodeConfig(
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="ubuntu:latest",
        )

        infra_config = InfConfig([config1, config1, config2, config2])

        infrasturcture = deployer.deploy_infrastructure(infra_config)
        infrasturcture.start()

        client = docker.from_env()
        try:
            expected_names = {
                "docker_node_0_container",
                "docker_node_1_container",
                "docker_node_2_container",
                "docker_node_3_container",
            }

            containers = client.containers.list(all=True)
            our_containers = [c for c in containers if c.name in expected_names]

            assert len(our_containers) == 4, (
                f"expected 2 containers, found "
                f"{len(our_containers)}: {[c.name for c in our_containers]}"
            )

            actual_names = {c.name for c in our_containers}
            assert actual_names == expected_names
        finally:
            client.close()

        assert infrasturcture.stop(3)

        assert infrasturcture.get_usable()

        deployer.destroy_everything()

        client = docker.from_env()

        expected_container_names = {
            "docker_node_0_container",
            "docker_node_1_container",
            "docker_node_2_container",
            "docker_node_3_container",
        }

        containers = client.containers.list(all=True)
        our_containers = [c for c in containers if c.name in expected_container_names]

        client.close()

        assert len(our_containers) == 0

        assert len(deployer.get_images()) == 0  # type: ignore

        assert len(deployer.get_nodes()) == 0  # type: ignore

        assert not (infrasturcture.start())

        assert not (infrasturcture.get_usable())

    def test_node_update_configuration(self, deployer: DockerDeployer):
        config = NodeConfig(
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="alpine:latest",
        )

        wrong_config = NodeConfig(
            cpu_limit=-1,
            ram_limit="512m",
            disk_limit="",
            os_name="",
        )

        correct_new_config = NodeConfig(
            cpu_limit=2,
            ram_limit="512m",
            disk_limit="",
            os_name="",
        )

        node = deployer.deploy_node(config)

        # there is no any running containers
        assert not (node.update_configuration(correct_new_config))

        node.start()

        # wrong cpu-limit value
        assert not (node.update_configuration(wrong_config))

        assert node.update_configuration(correct_new_config)

        assert node.current_cpu_limit() == 2

        assert node.current_mem_limit() == "512m"

        node.stop(1)

        assert node.update_configuration(correct_new_config)

        deployer.destroy_everything()

    def test_infrastucture_update_configuration(self, deployer: DockerDeployer):
        config = NodeConfig(
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="alpine:latest",
        )

        infra_config = InfConfig([config])

        infrastructure = deployer.deploy_infrastructure(inf_config=infra_config)

        nodes = infrastructure.get_nodes()

        assert len(nodes) == 1

        node_to_upd = list(nodes.keys())[0]

        wrong_config = NodeConfig(
            cpu_limit=-1,
            ram_limit="512m",
            disk_limit="",
            os_name="",
        )

        correct_new_config = NodeConfig(
            cpu_limit=2,
            ram_limit="512m",
            disk_limit="",
            os_name="",
        )

        # there is no any running containers
        assert not (
            infrastructure.update_configuration(correct_new_config, node_to_upd)
        )

        infrastructure.start()

        assert not (infrastructure.update_configuration(wrong_config, node_to_upd))

        assert infrastructure.update_configuration(correct_new_config, node_to_upd)

        infrastructure.stop(1)

        assert infrastructure.update_configuration(correct_new_config, node_to_upd)

        deployer.destroy_everything()
