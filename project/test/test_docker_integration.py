"""
pytest -m integration test/integration/test_docker_integration.py -v
"""

import docker
import pytest
import os
import pathlib
import tarfile
import uuid
import tempfile

from pg_polygon_orchestr import NodeConfig
from pg_polygon_orchestr import NetConfig
from pg_polygon_orchestr import VolumeConfig
from pg_polygon_orchestr import DockerDeployer
from pg_polygon_orchestr import common_exceptions, docker_exceptions
from pg_polygon_orchestr import ExecResult, MountConfig
from pg_polygon_orchestr import list_snapshots, SnapshotInfraBuilder, find_snap_desc
from pg_polygon_orchestr import HostPathDesc

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

# ------ ФИКСТУРЫ И ДАННЫЕ


@pytest.fixture
def deployer():
    d = DockerDeployer()
    yield d
    d.remove_infrastructure()


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


CONTAINER_MOUNT_DIR = "/mnt/test_data"
CONTAINER_MOUNT_FILE = "/mnt/test_file.txt"

# ------ ТЕСТЫ


@skip_if_no_docker
class TestDockerDeployerIntegration:

    # ----- БАЗОВЫЙ ФУНКЦИОНАЛ

    def test_1__two_nodes_deployed_started_named_and_destroyed(
        self, deployer: DockerDeployer
    ):
        # конфиг для двух нод
        config1 = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine:latest",
        )

        node_a = deployer.put_node_config(name="node_a", config=config1)
        node_b = deployer.put_node_config(name="node_b", config=config1)

        assert node_a is not None
        assert node_b is not None

        # проверяем что не можем запустить ноду пока та не задеплоена
        with pytest.raises(common_exceptions.EntityIsNotDeployed):
            node_a.start()

        # деплой и запуск контейнеров
        deployer.deploy_infrastructure()

        with pytest.raises(common_exceptions.EntityIsAlreadyDeployed):
            node_a.deploy()

        node_a.start()
        node_b.start()

        # проверка, что все контейнеры запустились и работают
        client = docker.from_env()
        try:
            expected_names = {
                node_a.real_name(),
                node_b.real_name(),
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

        # очистка ресурсов
        deployer.remove_infrastructure()

        with pytest.raises(common_exceptions.EntityIsRemovedException):
            node_a.start()

        client = docker.from_env()

        # имеющиеся контейнеры
        expected_container_names = {
            node_a.real_name(),
            node_b.real_name(),
        }
        containers = client.containers.list(all=True)
        infra_containers = [c for c in containers if c.name in expected_container_names]

        client.close()

    def test_2__four_nodes_with_different_configs_start_stop_destroy(
        self, deployer: DockerDeployer
    ):
        # конфиг для первых двух нод
        config1 = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine:latest",
        )

        # конфиг для двух последних нод
        config2 = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="ubuntu:latest",
        )

        # деплой и старт инфраструктуры
        node_a = deployer.put_node_config(name="node_a", config=config1)
        node_b = deployer.put_node_config(name="node_b", config=config1)
        node_c = deployer.put_node_config(name="node_c", config=config2)
        node_d = deployer.put_node_config(name="node_d", config=config2)

        deployer.deploy_infrastructure()

        for node in [node_a, node_b, node_c, node_d]:
            node.start()

        # проверка что инфраструктура запустилась и все контейнеры работают
        client = docker.from_env()
        try:
            expected_names = {
                node_a.real_name(),
                node_b.real_name(),
                node_c.real_name(),
                node_d.real_name(),
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

        # останавливаем работу инфраструктуры
        for node in [node_a, node_b, node_c, node_d]:
            node.stop(1)

        deployer.remove_infrastructure()

        # получаем имеющиеся контейнеры
        client = docker.from_env()

        expected_container_names = {
            node_a.real_name(),
            node_b.real_name(),
            node_c.real_name(),
            node_d.real_name(),
        }

        containers = client.containers.list(all=True)
        infra_containers = [c for c in containers if c.name in expected_container_names]
        client.close()

    def test_3__node_update_configuration(self, deployer: DockerDeployer):
        # изначальный конфиг ноды
        config = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine",
        )

        # корректный конфиг для обновления
        new_config = NodeConfig(
            cpu_limit=2,
            mem_limit="512m",
            os="debian",
        )

        node = deployer.put_node_config(name="node", config=config)
        assert node

        deployer.deploy_infrastructure()

        node.start()

        # проверка, что обновление конфигурации произошло штатно
        node.update(new_config)

        checker = docker.from_env()
        try:
            container = checker.containers.get(container_id=node.real_name())
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

        print(deployer.get_nodes())

        with pytest.raises(common_exceptions.EntityIsRemovedException):
            node.update(new_config=new_config)

        node = deployer.put_node_config(name="node", config=config)
        print(node.state().name)
        node.update(new_config=new_config)

        deployer.deploy_infrastructure()

        node.start()

        checker = docker.from_env()
        try:
            container = checker.containers.get(container_id=node.real_name())
            host_config = container.attrs["HostConfig"]
            cpu_period = host_config["CpuPeriod"]
            cpu_quota = host_config["CpuQuota"]
            assert cpu_period == 100000
            assert cpu_quota == 100000 * new_config.cpu_limit
        finally:
            checker.close()

    def test_4__exec_simple_commands(self, deployer: DockerDeployer):
        # конфигурация для ноды
        config = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine",
        )

        node = deployer.put_node_config(name="node", config=config)

        with pytest.raises(common_exceptions.EntityIsNotDeployed):
            node.exec('echo "hello"')

        # деплоим ноду
        deployer.deploy_infrastructure()

        # проверяем что не даст исполнить команду на несуществующем контейнере
        with pytest.raises(docker_exceptions.ExecOnContainerError):
            node.exec('echo "hello"')

        node.start()
        node.stop(1)

        # на всякий случай вторая проверка, что не даст запустить на остановленном контейнере
        with pytest.raises(docker_exceptions.ExecOnContainerError):
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

        node.stop(0)
        deployer.clear_infrastructure()

        with pytest.raises(common_exceptions.EntityIsNotDeployed):
            node.exec('echo "hello"')

        deployer.remove_infrastructure()

        with pytest.raises(common_exceptions.EntityIsRemovedException):
            node.exec('echo "hello"')

    # ----- СЕТЕВЫЕ ТЕСТЫ

    def test_5__internal_network_with_two_containers(self, deployer: DockerDeployer):
        # конфигурируем ноды
        config = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine",
            connect_to_docker_default=False,
        )

        a = deployer.put_node_config(name="node_a", config=config)
        b = deployer.put_node_config(name="node_b", config=config)

        assert a and b

        # проверяем что инфраструктура смогла сконфигурировать сеть с корректным конфигом
        net_config = NetConfig(
            internal=True,
        )

        net = deployer.put_network_config(name="net", config=net_config)

        # деплоим инфраструктуру

        with pytest.raises(common_exceptions.EntityIsNotDeployed):
            net.connect_node(node=a)

        deployer.deploy_infrastructure()

        with pytest.raises(common_exceptions.ConnectToNetError):
            net.connect_node(node=a)

        with pytest.raises(common_exceptions.ConnectToNetError):
            net.connect_node(node=b)

        a.start()
        b.start()

        net.connect_node(node=a)
        net.connect_node(node=b)

        # проверяем что A видит B

        a_ping_b_result = a.exec(f"ping -c 1 {b.real_name()}")
        assert self.__check_exit_code(a_ping_b_result, 0, True)

        # проверяем что B видит A

        b_ping_a_result = b.exec(f"ping -c 1 {a.real_name()}")
        assert self.__check_exit_code(b_ping_a_result, 0, True)

        # проверяем что контейнеры не могут обращаться к внешним ресурсам (internal сеть)

        a_ping_google = a.exec("ping -c 3 8.8.8.8")
        b_ping_google = b.exec("ping -c 3 8.8.8.8")

        assert self.__check_exit_code(a_ping_google, 0, False)
        assert self.__check_exit_code(b_ping_google, 0, False)

        net.disconnect_node(node=a)

        a_ping_b_after_disconnect = a.exec(f"ping -c 1 {b.real_name()}")
        assert self.__check_exit_code(a_ping_b_after_disconnect, 0, False)

        net.disconnect_node(node=b)

        a.stop(1)
        a.clear()
        b.stop(1)
        b.clear()

        with pytest.raises(common_exceptions.ConnectToNetError):
            net.connect_node(node=a)

        with pytest.raises(common_exceptions.ConnectToNetError):
            net.connect_node(node=b)

    def test_6__public_network_with_three_containers(self, deployer: DockerDeployer):

        # конфиг ноды (не подключаемся к дефолтной сети, она здесь будет мешать, так как из неё можно выйти в интернет)
        config = NodeConfig(
            cpu_limit=1,
            mem_limit="512m",
            os="alpine:latest",
            connect_to_docker_default=False,
        )

        # конфигурируем ноды
        a = deployer.put_node_config(name="node_a", config=config)
        b = deployer.put_node_config(name="node_b", config=config)
        c = deployer.put_node_config(name="node_c", config=config)

        # конфигурируем сеть
        net_config = NetConfig(internal=False)

        net = deployer.put_network_config(name="net", config=net_config)

        # деплоим и запускаем инфраструктуру
        deployer.deploy_infrastructure()

        for node in [a, b, c]:
            node.start()

        net.connect_node(node=a)
        net.connect_node(node=b)
        net.connect_node(node=c)

        # пингуемся
        a_ping_b = a.exec(f"ping -c 1 {b.real_name()}")
        a_ping_c = a.exec(f"ping -c 1 {c.real_name()}")
        b_ping_a = b.exec(f"ping -c 1 {a.real_name()}")
        b_ping_c = b.exec(f"ping -c 1 {c.real_name()}")
        c_ping_a = c.exec(f"ping -c 1 {a.real_name()}")
        c_ping_b = c.exec(f"ping -c 1 {b.real_name()}")

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

    def test_7__four_nodes_and_four_networks(self, deployer: DockerDeployer):
        config = NodeConfig(
            cpu_limit=1,
            mem_limit="512m",
            os="ubuntu:latest",
            net_settings_roots=True,
            connect_to_docker_default=False,
            ip_forwarding=True,
        )

        a = deployer.put_node_config(name="node_a", config=config)
        b = deployer.put_node_config(name="node_b", config=config)
        c = deployer.put_node_config(name="node_c", config=config)
        d = deployer.put_node_config(name="node_d", config=config)

        net_config = NetConfig(internal=False)

        net1 = deployer.put_network_config(name="net1", config=net_config)
        net2 = deployer.put_network_config(name="net2", config=net_config)
        net3 = deployer.put_network_config(name="net3", config=net_config)
        net4 = deployer.put_network_config(name="net4", config=net_config)

        routes = [
            (a, c, b, net1, net2),
            (b, d, c, net2, net3),
            (c, a, d, net3, net4),
            (d, b, a, net4, net1),
        ]

        deployer.deploy_infrastructure()

        a.start()
        b.start()
        c.start()
        d.start()

        net1.connect_node(node=a)
        net1.connect_node(node=b)

        net2.connect_node(node=b)
        net2.connect_node(node=c)

        net3.connect_node(node=c)
        net3.connect_node(node=d)

        net4.connect_node(node=a)
        net4.connect_node(node=d)

        for node in [a, b, c, d]:
            node.exec(
                "sh -c 'apt-get update -qq && apt-get install -y iproute2 iputils-ping traceroute'"
            )

        for source, target, via_node, source_net, target_net in routes:
            target_ip = target_net.get_node_network_ip(node=target)
            via_ip = source_net.get_node_network_ip(node=via_node)
            target_subnet = target_net.get_network_ip()

            route_result = source.exec(f"ip route add {target_subnet} via {via_ip}")
            assert self.__check_exit_code(route_result, 0, True)

            ping_result = source.exec(f"ping -c 1 {target_ip}")
            assert self.__check_exit_code(ping_result, 0, True)

            traceroute_result = source.exec(f"traceroute -n {target_ip}")
            assert self.__check_exit_code(traceroute_result, 0, True)
            assert via_ip in traceroute_result.stdout  # type: ignore

        a.stop(0)
        b.stop(0)
        c.stop(0)
        d.stop(0)

        deployer.clear_infrastructure()

    # ----- ТЕСТЫ ДЛЯ ТОМОВ И ДИРЕКТОРИЙ

    def test_8__volume_mount_persistency(self, deployer: DockerDeployer):
        node_config = NodeConfig(cpu_limit=1, mem_limit="512m", os="ubuntu:latest")

        node = deployer.put_node_config(name="node", config=node_config)

        volume_conf = VolumeConfig(
            docker_volume_driver="local",
        )

        volume = deployer.put_volume_config(name="test_volume", config=volume_conf)

        deployer.deploy_infrastructure()

        mnt_config = MountConfig(
            mounted=volume,
            mount_path="/app/mounted_data",
            read_only=False,
        )

        node.start([mnt_config])

        result = node.exec("sh -c 'echo test > /app/mounted_data/file.txt'")
        assert self.__check_exit_code(result, 0, True)

        node.stop(1)
        node.start()

        result = node.exec("cat /app/mounted_data/file.txt")
        assert self.__check_exit_code(result, 0, True)
        assert "test" in result.stdout  # type: ignore

        node.stop(0)

        deployer.clear_infrastructure()

    def test_9__read_only_volume(self, deployer: DockerDeployer):
        node_config = NodeConfig(cpu_limit=1, mem_limit="512m", os="ubuntu:latest")

        node = deployer.put_node_config(name="node", config=node_config)

        volume_conf = VolumeConfig(docker_volume_driver="local")

        volume = deployer.put_volume_config(name="test_volume", config=volume_conf)

        deployer.deploy_infrastructure()

        mnt_config = MountConfig(
            mounted=volume,
            mount_path="/app/mounted_data",
            read_only=True,
        )

        node.start([mnt_config])

        result = node.exec("sh -c 'echo test > /app/mounted_data/file.txt'")
        assert self.__check_exit_code(result, 0, False)

        node.stop(0)
        deployer.clear_infrastructure()
        deployer.remove_infrastructure()

    def test_10__mount_directory_write_from_container_visible_on_host(
        self, deployer: DockerDeployer, host_temp_dir: str
    ):
        config = NodeConfig(os="alpine", cpu_limit=1, mem_limit="256m")

        node = deployer.put_node_config(name="test_node", config=config)

        filename = "from_container.txt"
        content = "written inside container"

        deployer.deploy_infrastructure()

        node.start(
            [
                MountConfig(
                    mounted=HostPathDesc(path=host_temp_dir),
                    mount_path=CONTAINER_MOUNT_DIR,
                    read_only=False,
                )
            ]
        )

        result = node.exec(
            command=f"sh -c \"echo -n '{content}' > {CONTAINER_MOUNT_DIR}/{filename}\""
        )

        assert self.__check_exit_code(exec_result=result, expected=0, equal=True)

        host_file_path = os.path.join(host_temp_dir, filename)
        assert os.path.exists(host_file_path)
        with open(host_file_path, "r") as f:
            actual_content = f.read()
        assert actual_content == content

    def test_11__mount_directory_write_from_host_visible_in_container(
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
        node.deploy()
        node.start(
            [
                MountConfig(
                    mounted=HostPathDesc(path=host_temp_dir),
                    mount_path=CONTAINER_MOUNT_DIR,
                    read_only=False,
                )
            ]
        )

        result = node.exec(command=f'sh -c "cat {CONTAINER_MOUNT_DIR}/{filename}"')

        assert self.__check_exit_code(exec_result=result, expected=0, equal=True)
        assert content in result.stdout

    def test_12__test_mount_single_file(
        self, deployer: DockerDeployer, host_temp_file: tuple[str, str]
    ):
        host_file_path, expected_content = host_temp_file

        config = NodeConfig(os="alpine", cpu_limit=1, mem_limit="256m")
        node = deployer.put_node_config(name="test_node", config=config)
        node.deploy()
        node.start(
            [
                MountConfig(
                    mounted=HostPathDesc(path=host_file_path),
                    mount_path=CONTAINER_MOUNT_FILE,
                    read_only=False,
                )
            ]
        )

        result = node.exec(f'sh -c "cat {CONTAINER_MOUNT_FILE}"')

        assert self.__check_exit_code(exec_result=result, expected=0, equal=True)
        assert expected_content == result.stdout

        assert os.path.exists(host_file_path)
        with open(host_file_path, "r") as f:
            assert f.read() == expected_content

    def test_13__test_mount_nonexistent_directory_raises(
        self, deployer: DockerDeployer, nonexistent_host_path: str
    ):
        config = NodeConfig(os="alpine", cpu_limit=1, mem_limit="256m")
        node = deployer.put_node_config(name="test_node", config=config)
        node.deploy()
        with pytest.raises(docker_exceptions.DockerContStartError):
            node.start(
                [
                    MountConfig(
                        mounted=HostPathDesc(path=nonexistent_host_path),
                        mount_path=CONTAINER_MOUNT_DIR,
                        read_only=False,
                    )
                ]
            )

        assert not os.path.exists(nonexistent_host_path)

    # ----- ТЕСТЫ ДЛЯ ЭКСПЕРИМЕНТОВ

    def test___two_internal_networks_and_switch(self, deployer: DockerDeployer):
        node_config = NodeConfig(
            os="alpine",
            cpu_limit=1,
            mem_limit="256m",
            net_settings_roots=True,
            connect_to_docker_default=False,
        )

        switch_config = NodeConfig(
            os="alpine",
            cpu_limit=1,
            mem_limit="256m",
            ip_forwarding=True,
            connect_to_docker_default=False,
        )

        net_config = NetConfig(internal=False)

        a = deployer.put_node_config(name="node_a", config=node_config)
        b = deployer.put_node_config(name="node_b", config=node_config)
        c = deployer.put_node_config(name="node_c", config=node_config)
        d = deployer.put_node_config(name="node_d", config=node_config)

        switch = deployer.put_node_config(name="switch", config=switch_config)

        net1 = deployer.put_network_config(name="net_1", config=net_config)
        net2 = deployer.put_network_config(name="net_2", config=net_config)

        deployer.deploy_infrastructure()

        a.start()
        b.start()
        c.start()
        d.start()

        net1.connect_node(node=a)
        net1.connect_node(node=b)

        net2.connect_node(node=c)
        net2.connect_node(node=d)

        switch.start()

        net1.connect_node(node=switch)
        net2.connect_node(node=switch)

        a_ip = net1.get_node_network_ip(node=a)
        b_ip = net1.get_node_network_ip(node=b)
        c_ip = net2.get_node_network_ip(node=c)
        d_ip = net2.get_node_network_ip(node=d)
        switch_net1_ip = net1.get_node_network_ip(node=switch)
        switch_net2_ip = net2.get_node_network_ip(node=switch)
        net1_ip = net1.get_network_ip()
        net2_ip = net2.get_network_ip()

        for node_net_1 in [a, b]:
            net_2_route = node_net_1.exec(
                f"ip route add {net2_ip} via {switch_net1_ip}"
            )

            assert self.__check_exit_code(net_2_route, 0, True)

        for node_net_2 in [c, d]:
            net_1_route = node_net_2.exec(
                f"ip route add {net1_ip} via {switch_net2_ip}"
            )

            assert self.__check_exit_code(net_1_route, 0, True)

        a_ping_b = a.exec(f"ping -c 1 {b.real_name()}")
        b_ping_a = b.exec(f"ping -c 1 {a.real_name()}")

        assert self.__check_exit_code(a_ping_b, 0, True)
        assert self.__check_exit_code(b_ping_a, 0, True)

        c_ping_d = c.exec(f"ping -c 1 {d.real_name()}")
        d_ping_c = d.exec(f"ping -c 1 {c.real_name()}")

        assert self.__check_exit_code(c_ping_d, 0, True)
        assert self.__check_exit_code(d_ping_c, 0, True)

        for net1_node in [a, b]:
            ping_c = net1_node.exec(f"ping -c 1 {c_ip}")

            assert self.__check_exit_code(ping_c, 0, True)

            ping_d = net1_node.exec(f"ping -c 1 {d_ip}")

            assert self.__check_exit_code(ping_d, 0, True)

        for net2_node in [c, d]:
            ping_a = net2_node.exec(f"ping -c 1 {a_ip}")

            assert self.__check_exit_code(ping_a, 0, True)

            ping_b = net2_node.exec(f"ping -c 1 {b_ip}")

            assert self.__check_exit_code(ping_b, 0, True)

        for node in [a, b, c, d, switch]:
            node.stop(0)

        deployer.clear_infrastructure()

    # ----- ТЕСТЫ ДЛЯ СНЭПШОТОВ

    def test___snapshot_archive_exists(self, deployer: DockerDeployer):
        node_config = NodeConfig(os="alpine", cpu_limit=1, mem_limit="256m")

        net_config = NetConfig(internal=False)

        volume_config = VolumeConfig(docker_volume_driver="local")

        node = deployer.put_node_config("node_a", config=node_config)
        net = deployer.put_network_config("net", config=net_config)
        vol = deployer.put_volume_config("vol", config=volume_config)

        node.deploy()
        net.deploy()
        vol.deploy()

        node.start(
            [
                MountConfig(
                    mounted=vol,
                    mount_path="/app/data",
                    read_only=False,
                )
            ]
        )

        net.connect_node(node=node)

        deployer.make_snapshot()

        snapshot_dir = os.path.join(
            pathlib.Path.home(), ".pg-polygon-orchestr", "snapshots"
        )

        assert os.path.exists(path=snapshot_dir)

        assert os.path.exists(
            os.path.join(snapshot_dir, f"{str(deployer.get_id())}.tar.gz")
        )

        os.remove(path=os.path.join(snapshot_dir, f"{str(deployer.get_id())}.tar.gz"))

        deployer.make_snapshot(snapshot_name="my_test_snapshot", online=True)

        assert not os.path.exists(
            os.path.join(snapshot_dir, f"{str(deployer.get_id())}.tar.gz")
        )

        assert os.path.exists(os.path.join(snapshot_dir, "my_test_snapshot.tar.gz"))

        os.remove(path=os.path.join(snapshot_dir, "my_test_snapshot.tar.gz"))

    def test___check_snapshot_archive_internals(self, deployer: DockerDeployer):
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

        a_id = node_a.get_id()
        b_id = node_b.get_id()
        c_id = node_c.get_id()
        net_id = net.get_id()
        vol_id = vol.get_id()

        deployer.deploy_infrastructure()

        for n in [node_a, node_b, node_c]:
            n.start()

        net.connect_node(node=node_a)
        net.connect_node(node=node_c)

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

    def test___build_infrastructire_from_snapshot(self, deployer: DockerDeployer):
        node_config = NodeConfig(os="alpine", cpu_limit=1, mem_limit="256m")
        net_config = NetConfig(internal=False)
        volume_config = VolumeConfig(docker_volume_driver="local")

        node_a = deployer.put_node_config("node_a", config=node_config)
        node_b = deployer.put_node_config("node_b", config=node_config)
        node_c = deployer.put_node_config("node_c", config=node_config)
        net = deployer.put_network_config("net", config=net_config)
        vol = deployer.put_volume_config("vol", config=volume_config)

        deployer.deploy_infrastructure()

        mcfg = MountConfig(
            mounted=vol,
            mount_path="/app/data",
            read_only=False,
        )

        for node in [node_a, node_b, node_c]:
            node.start([mcfg])

        net.connect_node(node=node_a)
        net.connect_node(node=node_b)
        net.connect_node(node=node_c)

        for node in [node_a, node_b, node_c]:
            pwd_res = node.exec(command="pwd")
            assert self.__check_exit_code(exec_result=pwd_res, expected=0, equal=True)
            pwd = pwd_res.stdout.strip()  # type: ignore

            tres = node.exec(command=f"touch {pwd}/text.txt")
            assert self.__check_exit_code(exec_result=tres, expected=0, equal=True)

            echo = node.exec(
                command=f"sh -c \"echo '{node.inf_name()}' > {pwd}/text.txt\""
            )
            assert self.__check_exit_code(exec_result=echo, expected=0, equal=True)

        deployer.make_snapshot(snapshot_name="my_snapshot", online=True)
        deployer.remove_infrastructure()

        snapshots = list_snapshots()
        assert len(snapshots) > 0
        assert "my_snapshot" in [sd.name for sd in snapshots]

        snapshot = find_snap_desc(target="my_snapshot")
        assert snapshot

        loaded_infra = SnapshotInfraBuilder().build(snapshot_desc=snapshot)
        assert len(loaded_infra.get_nodes().items()) == 3
        assert len(loaded_infra.get_network().items()) == 1
        assert len(loaded_infra.get_volumes().items()) == 1

        loaded_nodes = list(loaded_infra.get_nodes().values())

        for i in range(len(loaded_nodes)):
            node = loaded_nodes[i]

            pwd_res = node.exec(command="pwd")
            assert self.__check_exit_code(exec_result=pwd_res, expected=0, equal=True)
            pwd = pwd_res.stdout.strip()  # type: ignore

            cat = node.exec(command=f"cat {pwd}/text.txt")
            assert self.__check_exit_code(exec_result=cat, expected=0, equal=True)
            assert f"{node.inf_name()}" in cat.stdout  # type: ignore

            ping_1 = node.exec(
                command=f"ping -c 1 {loaded_nodes[(i + 1) % 3].real_name()}"
            )
            ping_2 = node.exec(
                command=f"ping -c 1 {loaded_nodes[(i + 2) % 3].real_name()}"
            )
            assert self.__check_exit_code(exec_result=ping_1, expected=0, equal=True)
            assert self.__check_exit_code(exec_result=ping_2, expected=0, equal=True)

        loaded_infra.remove_infrastructure()

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

    def __check_node_data_in_snapshot_names(
        self, uuid: uuid.UUID, names: list[str], check_fs_archive: bool = True
    ):
        return f"nodes/{str(uuid)}.json" in names and (
            (f"nodes/{str(uuid)}.tar" in names) if check_fs_archive else True
        )
