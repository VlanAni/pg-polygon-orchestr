"""
pytest -m integration test/integration/test_docker_integration.py -v
"""

import docker
import pytest

from pg_polygon_orchestr.core.configs.node_config import NodeConfig
from pg_polygon_orchestr.core.configs.net_config import NetConfig
from pg_polygon_orchestr.core.configs.infra_config import InfConfig
from pg_polygon_orchestr.core.configs.docker_volume_config import VolumeConfig
from pg_polygon_orchestr.core.deployers.docker_deployer import DockerDeployer

from pg_polygon_orchestr.core.exception import common_exceptions

from pg_polygon_orchestr.core.nodes.exec_result import ExecResult

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

    # ----- БАЗОВЫЙ ФУНКЦИОНАЛ

    def test_1__two_nodes_deployed_started_named_and_destroyed(
        self, deployer: DockerDeployer
    ):
        # конфиг для двух нод
        config1 = NodeConfig(
            name="node_a",
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="alpine:latest",
        )

        config2 = NodeConfig(
            name="node_b",
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="alpine:latest",
        )

        inf_config = InfConfig()
        node_a = inf_config.put_node_config(config=config1)
        node_b = inf_config.put_node_config(config=config2)

        assert node_a is not None
        assert node_b is not None

        # деплой и запуск контейнеров
        _ = deployer.deploy_infrastructure(inf_config=inf_config)
        node_a.start()
        node_b.start()

        # проверка, что все контейнеры запустились и работают
        client = docker.from_env()
        try:
            expected_names = {
                "node_a",
                "node_b",
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

        # очистка ресурсов
        deployer.destroy_everything()
        client = docker.from_env()

        # имеющиеся контейнеры
        expected_container_names = {
            "node_a",
            "node_b",
        }
        containers = client.containers.list(all=True)
        our_containers = [c for c in containers if c.name in expected_container_names]

        client.close()

    def test_2__infrastructure_four_nodes_start_stop_destroy(
        self, deployer: DockerDeployer
    ):
        # конфиг для первых двух нод
        config1 = NodeConfig(
            name="node_a",
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="alpine:latest",
        )

        # конфиг для двух последних нод
        config2 = NodeConfig(
            name="node_b",
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="ubuntu:latest",
        )

        # конфиг для двух последних нод
        config3 = NodeConfig(
            name="node_c",
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="ubuntu:latest",
        )

        # конфиг для двух последних нод
        config4 = NodeConfig(
            name="node_d",
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="ubuntu:latest",
        )

        # деплой и старт инфраструктуры
        infra_config = InfConfig()
        node_a = infra_config.put_node_config(config1)
        node_b = infra_config.put_node_config(config2)
        node_c = infra_config.put_node_config(config3)
        node_d = infra_config.put_node_config(config4)
        assert node_a
        assert node_b
        assert node_c
        assert node_d

        infrasturcture = deployer.deploy_infrastructure(infra_config)

        node_a.start()
        node_b.start()
        node_c.start()
        node_d.start()

        # проверка что инфраструктура запустилась и все контейнеры работают
        client = docker.from_env()
        try:
            expected_names = {
                "node_a",
                "node_b",
                "node_c",
                "node_d",
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

        # проверяем что инфраструктура пригода к использованию
        assert infrasturcture.is_alive()

        # останавливаем работу инфраструктуры
        node_a.stop(1)
        node_b.stop(1)
        node_c.stop(1)
        node_d.stop(1)

        # очистка ресурсов
        deployer.destroy_everything()

        # получаем имеющиеся контейнеры
        client = docker.from_env()
        expected_container_names = {
            "node_a",
            "node_b",
            "node_c",
            "node_d",
        }
        containers = client.containers.list(all=True)
        our_containers = [c for c in containers if c.name in expected_container_names]
        client.close()

    def test_3__node_update_configuration(self, deployer: DockerDeployer):
        try:
            # изначальный конфиг ноды
            config = NodeConfig(
                name="node_a",
                cpu_limit=1,
                ram_limit="256m",
                disk_limit="1g",
                os_name="alpine:latest",
            )

            # конфиг с отрицательным ограничением на CPU
            wrong_config = NodeConfig(
                name="node_a",
                cpu_limit=-1,
                ram_limit="512m",
                disk_limit="",
                os_name="",
            )

            # корректный конфиг для обновления
            correct_new_config = NodeConfig(
                name="node_a",
                cpu_limit=2,
                ram_limit="512m",
                disk_limit="",
                os_name="",
            )

            inf_config = InfConfig()
            node = inf_config.put_node_config(config=config)
            assert node

            deployer.deploy_infrastructure(inf_config=inf_config)

            # у ноды нет контейнеров, поэтому обновлять конфигурацию
            with pytest.raises(common_exceptions.FailedToUpdateConfiguration):
                node.update_configuration(correct_new_config)

            node.start()

            # проверка что при обновлении конфигурации выикнулось исключение о неправильном лимите CPU
            with pytest.raises(common_exceptions.FailedToUpdateConfiguration):
                assert not (node.update_configuration(wrong_config))

            node.stop(0)

            # проверка, что обновление конфигурации произошло штатно
            node.update_configuration(correct_new_config)

        finally:
            # очистка ресурсов
            deployer.destroy_everything()

    def test_4__exec_simple_commands(self, deployer: DockerDeployer):
        try:
            # конфигурация для ноды
            config = NodeConfig(
                name="noda_a",
                cpu_limit=1,
                ram_limit="256m",
                disk_limit="",
                os_name="alpine:latest",
            )

            inf_config = InfConfig()
            node = inf_config.put_node_config(config=config)
            assert node

            # деплоим ноду
            _ = deployer.deploy_infrastructure(inf_config=inf_config)

            # проверяем что не даст исполнить команду на несуществующем контейнере
            with pytest.raises(common_exceptions.FailedToExecuteCommand):
                node.exec('echo "hello"')

            node.start()
            node.stop(1)

            # на всякий случай вторая проверка, что не даст запустить на остановленном контейнере
            with pytest.raises(common_exceptions.FailedToExecuteCommand):
                node.exec('echo "hello"')

            node.start()

            # проверка результата (должна выполниться команда)
            result = node.exec("ls ./not_exist")

            assert result is not None
            assert result.exit_code is not None and result.exit_code != 0
            assert result.execution_time > 0

            result = node.exec('echo "hello"')

            # команда выполнилась и вернула ноль как код возврата
            assert result is not None
            assert result.exit_code is not None and result.exit_code == 0
            assert "hello" in result.stdout and not (result.stderr)
            assert result.execution_time > 0

        finally:
            deployer.destroy_everything()

    # ----- СЕТЕВЫЕ ТЕСТЫ

    def test_5__internal_network_with_two_containers(self, deployer: DockerDeployer):
        inf_config = InfConfig()

        # конфигурируем ноды
        node_a = NodeConfig(
            name="node_a",
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="alpine:latest",
        )

        node_b = NodeConfig(
            name="node_b",
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="alpine:latest",
        )

        a = inf_config.put_node_config(config=node_a)
        b = inf_config.put_node_config(config=node_b)

        assert a and b

        # проверяем что инфраструктура не даёт сконфиругрировать сеть с несконфигурированными нодами
        bad_net_config = NetConfig(
            name="net", ipv6=False, internal=True, nodes=["node_ABC", "123"]
        )

        with pytest.raises(
            common_exceptions.NetConfigIncludeNotConfiguredNodeException
        ):
            inf_config.put_net_config(bad_net_config)

        # проверяем что инфраструктура смогла сконфигурировать сеть с корректным конфигом
        right_net_config = NetConfig(
            name="net", ipv6=False, internal=True, nodes=[a.get_name(), b.get_name()]
        )

        assert inf_config.put_net_config(right_net_config)

        # деплоим инфраструктуру

        _ = deployer.deploy_infrastructure(inf_config=inf_config)
        a.start()
        b.start()

        # проверяем что A видит B

        a_ping_b_result = a.exec("ping -c 1 node_b")
        assert self.__check_exit_code(a_ping_b_result, 0, True)

        # проверяем что B видит A

        b_ping_a_result = b.exec("ping -c 1 node_a")
        assert self.__check_exit_code(b_ping_a_result, 0, True)

        # проверяем что контейнеры не могут обращаться к внешним ресурсам (internal сеть)

        a_ping_google = a.exec("ping -c 3 8.8.8.8")
        b_ping_google = b.exec("ping -c 3 8.8.8.8")

        assert self.__check_exit_code(a_ping_google, 0, False)
        assert self.__check_exit_code(b_ping_google, 0, False)

        # очищаем ресурсы

        deployer.destroy_everything()

    def test_6__public_network_with_three_containers(self, deployer: DockerDeployer):

        inf_config = InfConfig()

        # конфиг ноды (не подключаемся к дефолтной сети, она здесь будет мешать, так как из неё можно выйти в интернет)
        node_a = NodeConfig(
            name="node_a",
            cpu_limit=1,
            ram_limit="512m",
            disk_limit="",
            os_name="alpine:latest",
            connect_to_docker_default_net=False,
        )

        node_b = NodeConfig(
            name="node_b",
            cpu_limit=1,
            ram_limit="512m",
            disk_limit="",
            os_name="alpine:latest",
            connect_to_docker_default_net=False,
        )

        node_c = NodeConfig(
            name="node_c",
            cpu_limit=1,
            ram_limit="512m",
            disk_limit="",
            os_name="alpine:latest",
            connect_to_docker_default_net=False,
        )

        # конфигурируем ноды
        a = inf_config.put_node_config(node_a)
        b = inf_config.put_node_config(node_b)
        c = inf_config.put_node_config(node_c)

        assert a and b and c

        # конфигурируем сеть
        net_config = NetConfig(
            name="net", ipv6=False, internal=False, nodes=["node_a", "node_b", "node_c"]
        )

        assert inf_config.put_net_config(net_config)

        # деплоим и запускаем инфраструктуру
        _ = deployer.deploy_infrastructure(inf_config=inf_config)
        a.start()
        b.start()
        c.start()

        # пингуемся
        a_ping_b = a.exec("ping -c 1 node_b")
        a_ping_c = a.exec("ping -c 1 node_c")
        b_ping_a = b.exec("ping -c 1 node_a")
        b_ping_c = b.exec("ping -c 1 node_c")
        c_ping_a = c.exec("ping -c 1 node_a")
        c_ping_b = c.exec("ping -c 1 node_b")

        # пропинговалися, проверяемся
        assert self.__check_exit_code(a_ping_b, 0, True)
        assert self.__check_exit_code(a_ping_c, 0, True)
        assert self.__check_exit_code(b_ping_a, 0, True)
        assert self.__check_exit_code(b_ping_c, 0, True)
        assert self.__check_exit_code(c_ping_a, 0, True)
        assert self.__check_exit_code(c_ping_b, 0, True)

        # пингуем гугл, должно пропинговаться
        a_ping_google = a.exec("ping -c 3 8.8.8.8")

        # пропинговались?
        assert self.__check_exit_code(a_ping_google, 0, True)

        deployer.destroy_everything()

    def test_7__four_nodes_and_four_networks(self, deployer: DockerDeployer):

        inf_config = InfConfig()

        node_a = NodeConfig(
            name="node_a",
            cpu_limit=1,
            ram_limit="512m",
            disk_limit="",
            os_name="ubuntu:latest",
            net_config_rights=True,
            connect_to_docker_default_net=True,
            ip_forwarding_on_node=True,
        )

        node_b = NodeConfig(
            name="node_b",
            cpu_limit=1,
            ram_limit="512m",
            disk_limit="",
            os_name="ubuntu:latest",
            net_config_rights=True,
            connect_to_docker_default_net=True,
            ip_forwarding_on_node=True,
        )

        node_c = NodeConfig(
            name="node_c",
            cpu_limit=1,
            ram_limit="512m",
            disk_limit="",
            os_name="ubuntu:latest",
            net_config_rights=True,
            connect_to_docker_default_net=True,
            ip_forwarding_on_node=True,
        )

        node_d = NodeConfig(
            name="node_d",
            cpu_limit=1,
            ram_limit="512m",
            disk_limit="",
            os_name="ubuntu:latest",
            net_config_rights=True,
            connect_to_docker_default_net=True,
            ip_forwarding_on_node=True,
        )

        a = inf_config.put_node_config(config=node_a)
        b = inf_config.put_node_config(config=node_b)
        c = inf_config.put_node_config(config=node_c)
        d = inf_config.put_node_config(config=node_d)

        assert a and b and c and d

        net_config_1 = NetConfig(
            name="1", ipv6=False, internal=False, nodes=["node_a", "node_b"]
        )
        net_config_2 = NetConfig(
            name="2", ipv6=False, internal=False, nodes=["node_b", "node_c"]
        )
        net_config_3 = NetConfig(
            name="3", ipv6=False, internal=False, nodes=["node_c", "node_d"]
        )
        net_config_4 = NetConfig(
            name="4", ipv6=False, internal=False, nodes=["node_d", "node_a"]
        )

        inf_config.put_net_config(config=net_config_1)
        inf_config.put_net_config(config=net_config_2)
        inf_config.put_net_config(config=net_config_3)
        inf_config.put_net_config(config=net_config_4)

        inf = deployer.deploy_infrastructure(inf_config=inf_config)

        a.start()
        b.start()
        c.start()
        d.start()

        package_update = a.exec(command="apt-get update -qq")
        assert self.__check_exit_code(package_update, 0, True)

        package_installation = a.exec(
            command="apt-get install -y iproute2 iputils-ping traceroute",
        )
        assert self.__check_exit_code(package_installation, 0, True)

        net_2_ip = inf.get_network_ip_addr("2")
        assert net_2_ip is not None

        node_c_ip_net_2 = inf.get_node_ip_in_network(
            node_name=c.get_name(), net_name="2"
        )
        assert node_c_ip_net_2 is not None

        node_b_ip_net_1 = inf.get_node_ip_in_network(
            node_name=b.get_name(), net_name="1"
        )
        assert node_b_ip_net_1 is not None

        result = a.exec(f"ip route add {net_2_ip} via {node_b_ip_net_1}")
        assert self.__check_exit_code(result, 0, True)

        a_ping_c = a.exec(f"ping -c 1 {node_c_ip_net_2}")
        assert self.__check_exit_code(a_ping_c, 0, True)

        a_traceroute_c = a.exec(f"traceroute {node_c_ip_net_2}")
        assert self.__check_exit_code(a_traceroute_c, 0, True)
        assert node_b_ip_net_1 in a_traceroute_c.stdout  # type: ignore

        deployer.destroy_everything()

    # ----- ТЕСТЫ ДЛЯ ТОМОВ

    def test_8__volume_mount_persistency(self, deployer: DockerDeployer):

        inf_config = InfConfig()

        node_config = NodeConfig(
            name="node", cpu_limit=1, ram_limit="512m", os_name="ubuntu:latest"
        )

        node = inf_config.put_node_config(config=node_config)
        assert node

        volume_conf = VolumeConfig(
            name="test_volume",
            owner_name="node",
            driver="local",
            mount_path="/app/mounted_data",
            read_only=False,
            delete_on_destroying=True,
        )

        assert inf_config.put_volume_config(config=volume_conf)

        _ = deployer.deploy_infrastructure(inf_config=inf_config)

        node.start()

        result = node.exec("sh -c 'echo test > /app/mounted_data/file.txt'")
        assert self.__check_exit_code(result, 0, True)

        node.stop(1)
        node.start()

        result = node.exec("cat /app/mounted_data/file.txt")
        assert self.__check_exit_code(result, 0, True)
        assert "test" in result.stdout  # type: ignore

        deployer.destroy_everything()

    def test_9_read_only_volume(self, deployer: DockerDeployer):

        inf_config = InfConfig()

        node_config = NodeConfig(
            name="node", cpu_limit=1, ram_limit="512m", os_name="ubuntu:latest"
        )

        node = inf_config.put_node_config(config=node_config)
        assert node

        volume_conf = VolumeConfig(
            name="test_volume",
            owner_name="node",
            driver="local",
            mount_path="/app/mounted_data",
            read_only=True,
            delete_on_destroying=True,
        )

        assert inf_config.put_volume_config(config=volume_conf)

        _ = deployer.deploy_infrastructure(inf_config=inf_config)

        node.start()

        result = node.exec("sh -c 'echo test > /app/mounted_data/file.txt'")
        assert self.__check_exit_code(result, 0, False)

        deployer.destroy_everything()

    # ----- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ

    def __check_exit_code(
        self, exec_result: ExecResult | None, expected: int, equal: bool
    ) -> bool:
        if exec_result is None:
            return False

        if exec_result.exit_code is None:
            return False

        return (exec_result.exit_code == expected and equal) or (
            exec_result.exit_code != expected and (not equal)
        )
