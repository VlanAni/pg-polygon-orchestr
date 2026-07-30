"""
pytest -m integration test/integration/test_docker_integration.py -v
"""

import docker
import pytest

from pg_polygon_orchestr.core.configs.node_config import NodeConfig
from pg_polygon_orchestr.core.configs.net_config import NetConfig
from pg_polygon_orchestr.core.configs.infra_config import InfConfig
from pg_polygon_orchestr.core.deployers.docker_deployer import DockerDeployer

from pg_polygon_orchestr.core.exception import docker_exceptions
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

    # БАЗОВЫЙ ФУНКЦИОНАЛ

    def test_1__two_nodes_deployed_started_named_and_destroyed(
        self, deployer: DockerDeployer
    ):
        # конфиг для двух нод
        config = NodeConfig(
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="alpine:latest",
        )

        # деплой и запуск контейнеров
        node_a = deployer.deploy_node("node_a", config)
        node_b = deployer.deploy_node("node_b", config)
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

        # проверка очистки ресурсов
        assert len(our_containers) == 0
        assert len(deployer.get_images()) == 0
        assert len(deployer.get_nodes()) == 0

    def test_2__infrastructure_four_nodes_start_stop_destroy(
        self, deployer: DockerDeployer
    ):
        # конфиг для первых двух нод
        config1 = NodeConfig(
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="alpine:latest",
        )

        # конфиг для двух последних нод
        config2 = NodeConfig(
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="ubuntu:latest",
        )

        # деплой и старт инфраструктуры
        infra_config = InfConfig()
        infra_config.put_node_config("node_a", config1)
        infra_config.put_node_config("node_b", config1)
        infra_config.put_node_config("node_c", config2)
        infra_config.put_node_config("node_d", config2)
        infrasturcture = deployer.deploy_infrastructure(infra_config)
        infrasturcture.start()

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
        assert infrasturcture.get_usable()

        # останавливаем работу инфраструктуры
        infrasturcture.stop(0)

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

        # проверка, что ресурсы очистились
        assert len(our_containers) == 0
        assert len(deployer.get_images()) == 0
        assert len(deployer.get_nodes()) == 0
        assert not (infrasturcture.get_usable())

    def test_3__node_update_configuration(self, deployer: DockerDeployer):
        try:
            # изначальный конфиг ноды
            config = NodeConfig(
                cpu_limit=1,
                ram_limit="256m",
                disk_limit="1g",
                os_name="alpine:latest",
            )

            # конфиг с отрицательным ограничением на CPU
            wrong_config = NodeConfig(
                cpu_limit=-1,
                ram_limit="512m",
                disk_limit="",
                os_name="",
            )

            # корректный конфиг для обновления
            correct_new_config = NodeConfig(
                cpu_limit=2,
                ram_limit="512m",
                disk_limit="",
                os_name="",
            )

            node = deployer.deploy_node("node_a", config)

            # у ноды нет контейнеров, поэтому обновлять конфигурацию
            with pytest.raises(docker_exceptions.NoDockerContainerToPerformOperation):
                node.update_configuration(correct_new_config)

            node.start()

            # проверка что при обновлении конфигурации выикнулось исключение о неправильном лимите CPU
            with pytest.raises(
                docker_exceptions.UpdateConfigurationCannotBePerfomedIfCpuLimitNotPositive
            ):
                assert not (node.update_configuration(wrong_config))

            # проверка что ресурсы обновились
            node.update_configuration(correct_new_config)
            assert node.current_cpu_limit() == 2
            assert node.current_mem_limit() == "512m"

            node.stop(0)

            # проверка, что обновление конфигурации произошло штатно
            node.update_configuration(correct_new_config)

        finally:
            # очистка ресурсов
            deployer.destroy_everything()

    def test_4__infrastucture_update_configuration(self, deployer: DockerDeployer):
        try:
            # конфиг ноды
            config = NodeConfig(
                cpu_limit=1,
                ram_limit="256m",
                disk_limit="",
                os_name="alpine:latest",
            )

            # конфигурируем и деплоим инфраструктуру
            infra_config = InfConfig()
            infra_config.put_node_config("node_a", config=config)
            infrastructure = deployer.deploy_infrastructure(inf_config=infra_config)

            # получаем ноды инфраструктуры
            nodes = infrastructure.get_nodes()

            # проверяем что нода одна
            assert len(nodes) == 1

            node_to_upd = "node_a"

            # плохой конфиг
            wrong_config = NodeConfig(
                cpu_limit=-1,
                ram_limit="512m",
                disk_limit="",
                os_name="",
            )

            # хороший конфиг
            correct_new_config = NodeConfig(
                cpu_limit=2,
                ram_limit="512m",
                disk_limit="",
                os_name="",
            )

            # пока нет запущенных контейнеров - не можем обновить инфраструктуру
            with pytest.raises(common_exceptions.FailedToUpdateConfiguration):
                infrastructure.update_configuration(correct_new_config, node_to_upd)

            # запускаем инфраструктуру
            infrastructure.start()

            # невозможно обновить конфигурацию, потому что она содержит плохие значения
            with pytest.raises(common_exceptions.FailedToUpdateConfiguration):
                infrastructure.update_configuration(wrong_config, node_to_upd)

            # корректное обновление конфигурации не вызывает исключений
            infrastructure.update_configuration(correct_new_config, node_to_upd)

            infrastructure.stop(1)

            # на всякий случай проверяем возможность обновить конфу для остановленного контейнера
            infrastructure.update_configuration(correct_new_config, node_to_upd)
        finally:
            deployer.destroy_everything()

    def test_5__exec_simple_commands(self, deployer: DockerDeployer):
        try:
            # конфигурация для ноды
            config = NodeConfig(
                cpu_limit=1,
                ram_limit="256m",
                disk_limit="",
                os_name="alpine:latest",
            )

            # деплоим ноду
            node_a = deployer.deploy_node(name="node_a", config=config)

            # проверяем что не даст исполнить команду на несуществующем контейнере
            with pytest.raises(
                docker_exceptions.CannotExecACommandOnNotRunningContainer
            ):
                node_a.exec('echo "hello"')

            node_a.start()
            node_a.stop(1)

            # на всякий случай вторая проверка, что не даст запустить на остановленном контейнере
            with pytest.raises(
                docker_exceptions.CannotExecACommandOnNotRunningContainer
            ):
                node_a.exec('echo "hello"')

            node_a.start()

            # проверка результата (должна выполниться команда)
            result = node_a.exec("ls ./not_exist")

            assert result is not None
            assert result.exit_code is not None and result.exit_code != 0
            assert result.execution_time > 0

            result = node_a.exec('echo "hello"')

            # команда выполнилась и вернула ноль как код возврата
            assert result is not None
            assert result.exit_code is not None and result.exit_code == 0
            assert "hello" in result.stdout and not (result.stderr)
            assert result.execution_time > 0

        finally:
            deployer.destroy_everything()

    def test_6__test_exec_for_infrastructure(self, deployer: DockerDeployer):
        try:
            # конфиг ноды
            config = NodeConfig(
                cpu_limit=1,
                ram_limit="256m",
                disk_limit="",
                os_name="alpine:latest",
            )

            # конфигурируем и деплоим инфраструктуру
            infra_config = InfConfig()
            infra_config.put_node_config("node_a", config=config)
            infrastructure = deployer.deploy_infrastructure(inf_config=infra_config)

            # не можем запустить команду на инфраструктуре где нет контейнеров
            with pytest.raises(common_exceptions.FailedToExecuteCommand):
                infrastructure.exec_command_on_node("node_a", 'echo "hello"')

            infrastructure.start()
            infrastructure.stop(1)

            # не можем запустить команду на инфраструктуре где нет запущенных контейнеров
            with pytest.raises(common_exceptions.FailedToExecuteCommand):
                infrastructure.exec_command_on_node("node_a", 'echo "hello"')

            infrastructure.start()

            # не можем запустить команду на несуществующей ноде
            with pytest.raises(common_exceptions.FailedToExecuteCommand):
                infrastructure.exec_command_on_node("node_b", 'echo "hello"')

            result = infrastructure.exec_command_on_node("node_a", 'echo "hello"')

            # команда выполнилась и вернула ноль как код возврата
            assert result is not None
            assert result.exit_code is not None and result.exit_code == 0
            assert "hello" in result.stdout and not (result.stderr)
            assert result.execution_time > 0
        finally:
            deployer.destroy_everything()

    # СЕТЕВЫЕ ТЕСТЫ

    def test_7__internal_network_with_two_containers(self, deployer: DockerDeployer):
        inf_config = InfConfig()

        # конфигурируем ноды
        node_config = NodeConfig(
            cpu_limit=1,
            ram_limit="256m",
            disk_limit="1g",
            os_name="alpine:latest",
        )

        inf_config.put_node_config("node_a", config=node_config)
        inf_config.put_node_config("node_b", config=node_config)

        # проверяем что инфраструктура не даёт сконфиругрировать сеть с несконфигурированными нодами
        bad_net_config = NetConfig(ipv6=False, internal=True, nodes=["node_ABC", "123"])

        with pytest.raises(
            common_exceptions.NetConfigIncludeNotConfiguredNodeException
        ):
            inf_config.put_net_config("net", bad_net_config)

        # проверяем что инфраструктура смогла сконфигурировать сеть с корректным конфигом
        right_net_config = NetConfig(
            ipv6=False, internal=True, nodes=["node_a", "node_b"]
        )

        assert inf_config.put_net_config("net_test_7", right_net_config)

        # деплоим инфраструктуру

        inf = deployer.deploy_infrastructure(inf_config=inf_config)
        inf.start()

        # проверяем что A видит B

        a_ping_b_result = inf.exec_command_on_node("node_a", "ping -c 1 node_b")

        assert self.__check_exit_code(a_ping_b_result, 0, True)

        # проверяем что B видит A

        b_ping_a_result = inf.exec_command_on_node("node_b", "ping -c 1 node_a")

        assert self.__check_exit_code(b_ping_a_result, 0, True)

        # проверяем что контейнеры не могут обращаться к внешним ресурсам (internal сеть)

        a_ping_google = inf.exec_command_on_node("node_a", "ping -c 3 8.8.8.8")
        b_ping_google = inf.exec_command_on_node("node_b", "ping -c 3 8.8.8.8")

        assert self.__check_exit_code(a_ping_google, 0, False)
        assert self.__check_exit_code(b_ping_google, 0, False)

        # очищаем ресурсы

        deployer.destroy_everything()

    def test_8__public_network_with_three_containers(self, deployer: DockerDeployer):

        inf_config = InfConfig()

        # конфиг ноды (не подключаемся к дефолтной сети, она здесь будет мешать, так как из неё можно выйти в интернет)
        node_config = NodeConfig(
            cpu_limit=1,
            ram_limit="512m",
            disk_limit="",
            os_name="alpine:latest",
            connect_to_docker_default_net=False,
        )

        # конфигурируем ноды
        inf_config.put_node_config("node_a", config=node_config)
        inf_config.put_node_config("node_b", config=node_config)
        inf_config.put_node_config("node_c", config=node_config)

        # конфигурируем сеть
        net_config = NetConfig(
            ipv6=False, internal=False, nodes=["node_a", "node_b", "node_c"]
        )

        assert inf_config.put_net_config("net_test_8", config=net_config)

        # деплоим и запускаем инфраструктуру
        inf = deployer.deploy_infrastructure(inf_config=inf_config)
        inf.start()

        # пингуемся
        a_ping_b = inf.exec_command_on_node("node_a", "ping -c 1 node_b")
        a_ping_c = inf.exec_command_on_node("node_a", "ping -c 1 node_c")
        b_ping_a = inf.exec_command_on_node("node_b", "ping -c 1 node_a")
        b_ping_c = inf.exec_command_on_node("node_b", "ping -c 1 node_c")
        c_ping_a = inf.exec_command_on_node("node_c", "ping -c 1 node_a")
        c_ping_b = inf.exec_command_on_node("node_c", "ping -c 1 node_b")

        # пропинговалися, проверяемся
        assert self.__check_exit_code(a_ping_b, 0, True)
        assert self.__check_exit_code(a_ping_c, 0, True)
        assert self.__check_exit_code(b_ping_a, 0, True)
        assert self.__check_exit_code(b_ping_c, 0, True)
        assert self.__check_exit_code(c_ping_a, 0, True)
        assert self.__check_exit_code(c_ping_b, 0, True)

        # пингуем гугл, должно пропинговаться
        a_ping_google = inf.exec_command_on_node("node_a", "ping -c 3 8.8.8.8")

        # пропинговались?
        assert self.__check_exit_code(a_ping_google, 0, True)

        deployer.destroy_everything()

    def test_9__four_nodes_and_four_networks(self, deployer: DockerDeployer):

        inf_config = InfConfig()

        node_config = NodeConfig(
            cpu_limit=1,
            ram_limit="512m",
            disk_limit="",
            os_name="ubuntu:latest",
            docker_net_admin_cap=True,
            connect_to_docker_default_net=True,
        )

        inf_config.put_node_config("node_a", config=node_config)
        inf_config.put_node_config("node_b", config=node_config)
        inf_config.put_node_config("node_c", config=node_config)
        inf_config.put_node_config("node_d", config=node_config)

        net_config_1 = NetConfig(ipv6=False, internal=False, nodes=["node_a", "node_b"])
        net_config_2 = NetConfig(ipv6=False, internal=False, nodes=["node_b", "node_c"])
        net_config_3 = NetConfig(ipv6=False, internal=False, nodes=["node_c", "node_d"])
        net_config_4 = NetConfig(ipv6=False, internal=False, nodes=["node_d", "node_a"])

        inf_config.put_net_config("1", config=net_config_1)
        inf_config.put_net_config("2", config=net_config_2)
        inf_config.put_net_config("3", config=net_config_3)
        inf_config.put_net_config("4", config=net_config_4)

        inf = deployer.deploy_infrastructure(inf_config=inf_config)

        inf.start()

        package_update = inf.exec_command_on_node(
            node_name="node_a", command="apt-get update -qq"
        )
        assert self.__check_exit_code(package_update, 0, True)

        package_installation = inf.exec_command_on_node(
            node_name="node_a", command="apt-get install -y iproute2 iputils-ping"
        )
        assert self.__check_exit_code(package_installation, 0, True)

        node_b_as_router = inf.exec_command_on_node(
            node_name="node_b", command="sysctl -w net.ipv4.ip_forward=1"
        )
        assert self.__check_exit_code(node_b_as_router, 0, True)

        net_2_ip = inf.get_network_ip_addr("2")
        assert net_2_ip is not None

        node_c_ip_net_2 = inf.get_node_ip_in_network(node_name="node_c", net_name="2")
        assert node_c_ip_net_2 is not None

        node_b_ip_net_1 = inf.get_node_ip_in_network(node_name="node_b", net_name="1")
        assert node_b_ip_net_1 is not None

        result = inf.exec_command_on_node(
            "node_a", f"ip route add {net_2_ip} via {node_b_ip_net_1}"
        )
        assert self.__check_exit_code(result, 0, True)

        a_ping_c = inf.exec_command_on_node("node_a", f"ping -c 1 {node_c_ip_net_2}")
        assert self.__check_exit_code(a_ping_c, 0, True)

        deployer.destroy_everything()

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
