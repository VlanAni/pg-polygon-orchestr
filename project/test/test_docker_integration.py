"""
pytest -m integration test/integration/test_docker_integration.py -v
"""

import docker
import pytest
import os
import pathlib
import tarfile
import uuid

from pg_polygon_orchestr import NodeConfig
from pg_polygon_orchestr import NetConfig
from pg_polygon_orchestr import VolumeConfig
from pg_polygon_orchestr import DockerDeployer
from pg_polygon_orchestr import common_exceptions, docker_exceptions
from pg_polygon_orchestr import ExecResult, MountConfig

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
    d.remove_infrastructure()


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

        node_a.start()
        node_b.start()

        # проверка, что все контейнеры запустились и работают
        client = docker.from_env()
        try:
            expected_names = {
                node_a.get_provider_path(),
                node_b.get_provider_path(),
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
        deployer.remove_infrastructure()

        with pytest.raises(common_exceptions.EntityIsRemovedException):
            node_a.start()

        client = docker.from_env()

        # имеющиеся контейнеры
        expected_container_names = {
            node_a.get_provider_path(),
            node_b.get_provider_path(),
        }
        containers = client.containers.list(all=True)
        our_containers = [c for c in containers if c.name in expected_container_names]

        client.close()

    def test_2__infrastructure_four_nodes_start_stop_destroy(
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

        node_a.start()
        node_b.start()
        node_c.start()
        node_d.start()

        # проверка что инфраструктура запустилась и все контейнеры работают
        client = docker.from_env()
        try:
            expected_names = {
                node_a.get_provider_path(),
                node_b.get_provider_path(),
                node_c.get_provider_path(),
                node_d.get_provider_path(),
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

        # останавливаем работу инфраструктуры
        node_a.stop(1)
        node_b.stop(1)
        node_c.stop(1)
        node_d.stop(1)

        deployer.remove_infrastructure()

        # получаем имеющиеся контейнеры
        client = docker.from_env()
        expected_container_names = {
            node_a.get_provider_path(),
            node_b.get_provider_path(),
            node_c.get_provider_path(),
            node_d.get_provider_path(),
        }
        containers = client.containers.list(all=True)
        our_containers = [c for c in containers if c.name in expected_container_names]
        client.close()

    def test_3__node_update_configuration(self, deployer: DockerDeployer):
        try:
            # изначальный конфиг ноды
            config = NodeConfig(
                cpu_limit=1,
                mem_limit="256m",
                os="alpine:latest",
            )

            # корректный конфиг для обновления
            new_config = NodeConfig(
                cpu_limit=2,
                mem_limit="512m",
                os="",
            )

            node = deployer.put_node_config(name="node", config=config)
            assert node

            deployer.deploy_infrastructure()

            node.start()

            # проверка, что обновление конфигурации произошло штатно
            node.update(new_config)

            checker = docker.from_env()

            container = checker.containers.get(container_id=node.get_provider_path())

            host_config = container.attrs["HostConfig"]

            cpu_period = host_config["CpuPeriod"]
            cpu_quota = host_config["CpuQuota"]

            assert cpu_period == 100000
            assert cpu_quota == 100000 * new_config.cpu_limit

            node.stop(0)
            node.clear()

            node.update(new_config=new_config)

            deployer.remove_infrastructure()

            with pytest.raises(common_exceptions.EntityIsRemovedException):
                node.update(new_config=new_config)

            # хорошо бы найти в будущем как извлечь лимит на память и посмотреть

        finally:
            # очистка ресурсов
            deployer.remove_infrastructure()

    def test_4__exec_simple_commands(self, deployer: DockerDeployer):
        try:
            # конфигурация для ноды
            config = NodeConfig(
                cpu_limit=1,
                mem_limit="256m",
                os="alpine:latest",
            )

            node = deployer.put_node_config(name="node", config=config)

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

        finally:
            deployer.remove_infrastructure()

    # ----- СЕТЕВЫЕ ТЕСТЫ

    def test_5__internal_network_with_two_containers(self, deployer: DockerDeployer):
        # конфигурируем ноды
        node_a_conf = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine:latest",
            connect_to_docker_default=False,
        )

        node_b_conf = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine:latest",
            connect_to_docker_default=False,
        )

        a = deployer.put_node_config(name="node_a", config=node_a_conf)
        b = deployer.put_node_config(name="node_b", config=node_b_conf)

        assert a and b

        # проверяем что инфраструктура смогла сконфигурировать сеть с корректным конфигом
        net_config = NetConfig(
            internal=True,
        )

        net = deployer.put_network_config(name="net", config=net_config)

        # деплоим инфраструктуру

        deployer.deploy_infrastructure()

        a.start()
        b.start()

        net.connect_node(node=a)
        net.connect_node(node=b)

        # проверяем что A видит B

        a_ping_b_result = a.exec(f"ping -c 1 {b.get_provider_path()}")
        assert self.__check_exit_code(a_ping_b_result, 0, True)

        # проверяем что B видит A

        b_ping_a_result = b.exec(f"ping -c 1 {a.get_provider_path()}")
        assert self.__check_exit_code(b_ping_a_result, 0, True)

        # проверяем что контейнеры не могут обращаться к внешним ресурсам (internal сеть)

        a_ping_google = a.exec("ping -c 3 8.8.8.8")
        b_ping_google = b.exec("ping -c 3 8.8.8.8")

        assert self.__check_exit_code(a_ping_google, 0, False)
        assert self.__check_exit_code(b_ping_google, 0, False)

        # очищаем ресурсы

        deployer.remove_infrastructure()

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
        a.start()
        b.start()
        c.start()

        net.connect_node(node=a)
        net.connect_node(node=b)
        net.connect_node(node=c)

        # пингуемся
        a_ping_b = a.exec(f"ping -c 1 {b.get_provider_path()}")
        a_ping_c = a.exec(f"ping -c 1 {c.get_provider_path()}")
        b_ping_a = b.exec(f"ping -c 1 {a.get_provider_path()}")
        b_ping_c = b.exec(f"ping -c 1 {c.get_provider_path()}")
        c_ping_a = c.exec(f"ping -c 1 {a.get_provider_path()}")
        c_ping_b = c.exec(f"ping -c 1 {b.get_provider_path()}")

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

        deployer.remove_infrastructure()

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

    # ----- ТЕСТЫ ДЛЯ ТОМОВ

    def test_8__volume_mount_persistency(self, deployer: DockerDeployer):
        node_config = NodeConfig(cpu_limit=1, mem_limit="512m", os="ubuntu:latest")

        node = deployer.put_node_config(name="node", config=node_config)

        volume_conf = VolumeConfig(
            docker_volume_driver="local",
        )

        volume = deployer.put_volume_config(name="test_volume", config=volume_conf)

        deployer.deploy_infrastructure()

        mnt_config = MountConfig(
            volume_host_path=volume.get_provider_path(),
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
            volume_host_path=volume.get_provider_path(),
            mount_path="/app/mounted_data",
            read_only=True,
        )

        node.start([mnt_config])

        result = node.exec("sh -c 'echo test > /app/mounted_data/file.txt'")
        assert self.__check_exit_code(result, 0, False)

        node.stop(0)
        deployer.clear_infrastructure()
        deployer.remove_infrastructure()

    # ----- ТЕСТЫ ДЛЯ ЭКСПЕРИМЕНТОВ

    def test_10__two_internal_networks_and_switch(self, deployer: DockerDeployer):
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

        a_ping_b = a.exec(f"ping -c 1 {b.get_provider_path()}")
        b_ping_a = b.exec(f"ping -c 1 {a.get_provider_path()}")

        assert self.__check_exit_code(a_ping_b, 0, True)
        assert self.__check_exit_code(b_ping_a, 0, True)

        c_ping_d = c.exec(f"ping -c 1 {d.get_provider_path()}")
        d_ping_c = d.exec(f"ping -c 1 {c.get_provider_path()}")

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

    def test_11_snapshot_archive_exists(self, deployer: DockerDeployer):
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
                    volume_host_path=vol.get_provider_path(),
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

    def test_12_check_snapshot_archive_internals(self, deployer: DockerDeployer):
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
