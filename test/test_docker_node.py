import docker
import pytest

from pg_polygon_orchestr import DockerDeployer
from pg_polygon_orchestr import NodeConfig
from pg_polygon_orchestr import common_exceptions, docker_exceptions

from .fixtures import deployer

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
class TestDockerNode:

    def test_BASIC_1__two_nodes_deployed_started_named_and_destroyed(
        self, deployer: DockerDeployer
    ):
        config1 = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine:latest",
        )

        node_a = deployer.put_node_config(name="node_a", config=config1)
        node_b = deployer.put_node_config(name="node_b", config=config1)

        assert node_a is not None
        assert node_b is not None

        with pytest.raises(common_exceptions.EntityIsNotDeployed):
            node_a.start()

        node_a.deploy()
        node_b.deploy()

        with pytest.raises(common_exceptions.EntityIsAlreadyDeployed):
            node_a.deploy()

        node_a.start()
        node_b.start()

        client = docker.from_env()
        try:
            expected_names = {
                node_a.real_name,
                node_b.real_name,
            }

            containers = client.containers.list(all=True)
            infra_containers = [c for c in containers if c.name in expected_names]

            assert len(infra_containers) == 2, (
                f"expected 2 containers, found "
                f"{len(infra_containers)}: {[c.name for c in infra_containers]}"
            )

            actual_names = {c.name for c in infra_containers}
            assert actual_names == expected_names
        finally:
            client.close()

        deployer.remove_infrastructure()

        with pytest.raises(common_exceptions.EntityIsRemovedException):
            node_a.start()

        client = docker.from_env()

        expected_container_names = {
            node_a.real_name,
            node_b.real_name,
        }
        containers = client.containers.list(all=True)
        infra_containers = [c for c in containers if c.name in expected_container_names]

        client.close()

    def test_BASIC_2__four_nodes_with_different_configs_start_stop_destroy(
        self, deployer: DockerDeployer
    ):
        config1 = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine:latest",
        )

        config2 = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="ubuntu:latest",
        )

        node_a = deployer.put_node_config(name="node_a", config=config1)
        node_b = deployer.put_node_config(name="node_b", config=config1)
        node_c = deployer.put_node_config(name="node_c", config=config2)
        node_d = deployer.put_node_config(name="node_d", config=config2)

        for node in [node_a, node_b, node_c, node_d]:
            node.deploy()
            node.start()

        client = docker.from_env()
        try:
            expected_names = {
                node_a.real_name,
                node_b.real_name,
                node_c.real_name,
                node_d.real_name,
            }

            containers = client.containers.list(all=True)
            infra_containers = [c for c in containers if c.name in expected_names]

            assert len(infra_containers) == 4, (
                f"expected 2 containers, found "
                f"{len(infra_containers)}: {[c.name for c in infra_containers]}"
            )

            actual_names = {c.name for c in infra_containers}
            assert actual_names == expected_names
        finally:
            client.close()

        for node in [node_a, node_b, node_c, node_d]:
            node.stop(1)

        deployer.remove_infrastructure()

        client = docker.from_env()

        expected_container_names = {
            node_a.real_name,
            node_b.real_name,
            node_c.real_name,
            node_d.real_name,
        }

        containers = client.containers.list(all=True)
        infra_containers = [c for c in containers if c.name in expected_container_names]
        client.close()

    def test_BASIC_3__node_update_configuration(self, deployer: DockerDeployer):
        config = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine",
        )

        new_config = NodeConfig(
            cpu_limit=2,
            mem_limit="512m",
            os="debian",
        )

        node = deployer.put_node_config(name="node", config=config)
        assert node

        node.deploy()
        node.start()

        node.update(new_config)

        checker = docker.from_env()
        try:
            container = checker.containers.get(container_id=node.real_name)
            host_config = container.attrs["HostConfig"]
            cpu_period = host_config["CpuPeriod"]
            cpu_quota = host_config["CpuQuota"]
            assert cpu_period == 100000
            assert cpu_quota == 100000 * new_config.cpu_limit
        finally:
            checker.close()

        node.stop(0)
        node.clear()

        node.update(new_config=new_config)

        deployer.remove_infrastructure()

        print(deployer.nodes)

        with pytest.raises(common_exceptions.EntityIsRemovedException):
            node.update(new_config=new_config)

        node = deployer.put_node_config(name="node", config=config)
        print(node.state.name)
        node.update(new_config=new_config)

        node.deploy()
        node.start()

        checker = docker.from_env()
        try:
            container = checker.containers.get(container_id=node.real_name)
            host_config = container.attrs["HostConfig"]
            cpu_period = host_config["CpuPeriod"]
            cpu_quota = host_config["CpuQuota"]
            assert cpu_period == 100000
            assert cpu_quota == 100000 * new_config.cpu_limit
        finally:
            checker.close()

    def test_BASIC_4__exec_simple_commands(self, deployer: DockerDeployer):
        config = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine",
        )

        node = deployer.put_node_config(name="node", config=config)

        with pytest.raises(common_exceptions.EntityIsNotDeployed):
            node.exec('echo "hello"')

        node.deploy()

        with pytest.raises(docker_exceptions.ExecOnContainerError):
            node.exec('echo "hello"')

        node.start()
        node.stop(1)

        with pytest.raises(docker_exceptions.ExecOnContainerError):
            node.exec('echo "hello"')

        node.start()

        result = node.exec("ls ./not_exist")

        assert result is not None
        assert result.exit_code is not None and result.exit_code != 0
        assert result.execution_time > 0

        result = node.exec('echo "hello"')

        assert result is not None
        assert result.exit_code is not None and result.exit_code == 0
        assert "hello" in result.stdout and not (result.stderr)
        assert result.execution_time > 0

        node.stop(0)
        deployer.clear_infrastructure()

        with pytest.raises(common_exceptions.EntityIsNotDeployed):
            node.exec('echo "hello"')

        deployer.remove_infrastructure()

        with pytest.raises(common_exceptions.EntityIsRemovedException):
            node.exec('echo "hello"')
