"""Регрессионные тесты для issue #43 «Исправить ошибки».

Нумерация тестов: ``test_REGR_<пункт issue>_<номер теста в пункте>__<описание>``.
Один пункт issue можно запустить целиком, например:

    uv run pytest -m integration -k REGR_3 -vv

Пункты issue:
    1 - ``network.connect/disconnect`` по имени узла (``Node | str``)
    2 - неудачный ``node.deploy()`` оставляет узел в состоянии ``DEPLOYED``
    3 - адреса не освобождаются при ``node.undeploy()`` / ``node.remove()``
    4 - ``make_snapshot`` при остановленных узлах / пустой инфраструктуре
    5 - ``node.update`` без ``cpu_limit`` / ``mem_limit``
    6 - ``destroy_infra`` останавливается на первой ошибке

Тесты описывают ожидаемое поведение ПОСЛЕ исправления. Решения, которые в issue
не зафиксированы, намеренно проверяются мягко (см. комментарии у
``DESTROY_ERRORS`` и в тестах пункта 5).
"""

import ipaddress
import os
import tarfile
import types
import uuid

import docker
import docker.errors
import pytest

from pg_polygon_orchestr import DockerDeployer
from pg_polygon_orchestr import NodeConfig
from pg_polygon_orchestr import NetConfig
from pg_polygon_orchestr import DockerNetworkConfigOptions
from pg_polygon_orchestr import SubnetConfig
from pg_polygon_orchestr import BindMount
from pg_polygon_orchestr import BindMountConfig
from pg_polygon_orchestr import common_exceptions, docker_exceptions
from pg_polygon_orchestr.core.common_types import EntityState
from pg_polygon_orchestr.core.common_types import SnapshotDescription

from .fixtures import deployer
from .fixtures import ipv4_subnet
from .fixtures import host_temp_dir
from .fixtures import generate_private_subnets
from .fixtures import check_exit_code

from .fixtures import CONTAINER_MOUNT_DIR

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

# Что именно должен бросить destroy_infra(), если часть ресурсов удалить не
# удалось, в issue не зафиксировано. Контракт `Deployer.destroy_infra` говорит
# про `RemoveError`; допускаем также `ClearError` (его бросают узлы и сети) и
# `ExceptionGroup` (если исправление агрегирует ошибки). Когда форма ошибки
# будет выбрана, кортеж стоит сузить до одного типа.
DESTROY_ERRORS = (
    common_exceptions.RemoveError,
    common_exceptions.ClearError,
    ExceptionGroup,
)


# ----- вспомогательные функции


def _node_config(**kwargs) -> NodeConfig:  # type: ignore
    return NodeConfig(base_image="alpine", cpu_limit=1, mem_limit="256m", **kwargs)  # type: ignore


def _deploy_net(net, subnet: ipaddress.IPv4Network, label: str = "1") -> None:  # type: ignore
    net.deploy(
        subnet_configs=[
            SubnetConfig(label=label, subnet=subnet, gateway=next(subnet.hosts()))
        ]
    )


def _free_hosts(subnet: ipaddress.IPv4Network, count: int):
    """Первые `count` адресов подсети после шлюза."""
    hosts = list(subnet.hosts())
    return hosts[1 : 1 + count]


def _container_exists(client: docker.DockerClient, name: str) -> bool:
    return any(c.name == name for c in client.containers.list(all=True))


def _network_exists(client: docker.DockerClient, name: str) -> bool:
    return any(n.name == name for n in client.networks.list())


def _volume_exists(client: docker.DockerClient, name: str) -> bool:
    return any(v.name == name for v in client.volumes.list())


def _images_with_prefix(client: docker.DockerClient, prefix: str) -> list[str]:
    return [
        tag
        for image in client.images.list()
        for tag in image.tags
        if tag.startswith(prefix)
    ]


def _host_config(container_name: str) -> dict:  # type: ignore
    client = docker.from_env()
    try:
        return client.containers.get(container_name).attrs["HostConfig"]  # type: ignore
    finally:
        client.close()


@pytest.fixture
def snapshot_name():
    """Уникальное имя снапшота; архив удаляется после теста, даже если он
    остался недописанным из-за ошибки."""
    name = f"regr_test_{uuid.uuid4().hex[:12]}"
    yield name
    path = SnapshotDescription(name=name).path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def blocked_infra(deployer: DockerDeployer):
    """Инфраструктура, в которой удаление сети `net_a` гарантированно падает.

    К `net_a` подключён контейнер, созданный в обход библиотеки: Docker не
    даёт удалить сеть с активными подключениями. В инфраструктуре также есть
    узел, вторая сеть `net_b` и том, которые удаляются без проблем.
    """
    subnets = generate_private_subnets(count=2)

    node = deployer.node_from_config(name="node", config=_node_config())
    net_a = deployer.network_from_config(
        name="net_a", config=NetConfig(DockerNetworkConfigOptions(internal=False))
    )
    net_b = deployer.network_from_config(
        name="net_b", config=NetConfig(DockerNetworkConfigOptions(internal=False))
    )
    vol = deployer.add_docker_volume(name="vol")

    node.deploy()
    node.start()
    _deploy_net(net_a, subnets[0])
    _deploy_net(net_b, subnets[1])
    vol.deploy()

    client = docker.from_env()
    blocker = client.containers.run(
        "alpine", "tail -f /dev/null", detach=True, network=net_a.real_name
    )

    infra = types.SimpleNamespace(
        node=node, net_a=net_a, net_b=net_b, vol=vol, blocker=blocker, client=client
    )

    try:
        yield infra
    finally:
        try:
            blocker.remove(force=True)
        except docker.errors.APIError:
            pass

        try:
            deployer.destroy_infra()
        except Exception:
            pass

        # страховка от утечек, если destroy_infra не справился
        for net in (net_a, net_b):
            if _network_exists(client, net.real_name):
                client.networks.get(net.real_name).remove()

        if _volume_exists(client, vol.real_name):
            client.volumes.get(vol.real_name).remove(force=True)

        client.close()


# ----- пункт 1: connect/disconnect по имени узла


@skip_if_no_docker
class TestConnectByNodeName:

    def test_REGR_1_1__connect_by_name_with_static_ip_and_communicate(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        a = deployer.node_from_config(name="node_a", config=_node_config())
        b = deployer.node_from_config(name="node_b", config=_node_config())
        net = deployer.network_from_config(
            name="net", config=NetConfig(DockerNetworkConfigOptions(internal=False))
        )

        a_ip, b_ip = _free_hosts(ipv4_subnet, 2)

        a.deploy()
        b.deploy()
        _deploy_net(net, ipv4_subnet)
        a.start()
        b.start()

        # `a` подключается по имени, `b` - по объекту
        net.connect(node="node_a", subnet_label="1", addr=a_ip)
        net.connect(node=b, subnet_label="1", addr=b_ip)

        assert net.get_node_connection_info(node=a).addr == a_ip
        assert net.get_node_connection_info(node=b).addr == b_ip

        assert check_exit_code(a.exec(f"ping -c 1 {b_ip}"), 0, True)
        assert check_exit_code(b.exec(f"ping -c 1 {a_ip}"), 0, True)

    def test_REGR_1_2__connect_by_name_without_address_allocates_one(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        node = deployer.node_from_config(name="node_a", config=_node_config())
        net = deployer.network_from_config(
            name="net", config=NetConfig(DockerNetworkConfigOptions(internal=False))
        )

        node.deploy()
        _deploy_net(net, ipv4_subnet)
        node.start()

        net.connect(node="node_a", subnet_label="1")

        info = net.get_node_connection_info(node=node)

        assert info.subnet_label == "1"
        assert info.addr in ipv4_subnet
        assert info.addr != next(ipv4_subnet.hosts())  # не адрес шлюза

    def test_REGR_1_3__disconnect_by_name_frees_the_address(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        node = deployer.node_from_config(name="node_a", config=_node_config())
        net = deployer.network_from_config(
            name="net", config=NetConfig(DockerNetworkConfigOptions(internal=False))
        )

        (static_ip,) = _free_hosts(ipv4_subnet, 1)

        node.deploy()
        _deploy_net(net, ipv4_subnet)
        node.start()

        net.connect(node="node_a", subnet_label="1", addr=static_ip)
        net.disconnect(node="node_a")

        with pytest.raises(docker_exceptions.GetContainerIpError):
            net.get_node_connection_info(node=node)

        # адрес освобождён - узел можно подключить заново на тот же адрес
        net.connect(node="node_a", subnet_label="1", addr=static_ip)

        assert net.get_node_connection_info(node=node).addr == static_ip

    def test_REGR_1_4__connect_by_unknown_name_raises(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        net = deployer.network_from_config(
            name="net", config=NetConfig(DockerNetworkConfigOptions(internal=False))
        )
        _deploy_net(net, ipv4_subnet)

        with pytest.raises(common_exceptions.ConnectToNetError):
            net.connect(node="no_such_node", subnet_label="1")

    def test_REGR_1_5__disconnect_by_unknown_name_raises(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        net = deployer.network_from_config(
            name="net", config=NetConfig(DockerNetworkConfigOptions(internal=False))
        )
        _deploy_net(net, ipv4_subnet)

        # сейчас для этого случая бросается ConnectToNetError, хотя логичнее
        # DisconnectFromNetError - тест не фиксирует этот выбор
        with pytest.raises((common_exceptions.DisconnectFromNetError)):
            net.disconnect(node="no_such_node")


# ----- пункт 2: неудачный deploy ноды


@skip_if_no_docker
class TestFailedNodeDeploy:

    @staticmethod
    def _duplicate_mounts(host_dir: str) -> list[BindMountConfig]:
        """Две точки монтирования с одним `dst`: Docker отвергает такой
        контейнер при создании, уже после того как образ узла собран."""
        mount = BindMountConfig(
            host_mnt=BindMount(src=host_dir), dst=CONTAINER_MOUNT_DIR
        )
        return [mount, mount]

    def test_REGR_2_1__failed_deploy_leaves_node_not_deployed(
        self, deployer: DockerDeployer, host_temp_dir: str
    ):
        node = deployer.node_from_config(name="node", config=_node_config())

        with pytest.raises(docker_exceptions.DockerDeployError):
            node.deploy(bind_mount_configs=self._duplicate_mounts(host_temp_dir))

        assert node.state is EntityState.NOT_DEPLOYED

    def test_REGR_2_2__after_failed_deploy_start_stop_exec_say_not_deployed(
        self, deployer: DockerDeployer, host_temp_dir: str
    ):
        node = deployer.node_from_config(name="node", config=_node_config())

        with pytest.raises(docker_exceptions.DockerDeployError):
            node.deploy(bind_mount_configs=self._duplicate_mounts(host_temp_dir))

        # а не AttributeError на отсутствующем контейнере
        with pytest.raises(common_exceptions.EntityIsNotDeployed):
            node.start()

        with pytest.raises(common_exceptions.EntityIsNotDeployed):
            node.stop(1)

        with pytest.raises(common_exceptions.EntityIsNotDeployed):
            node.exec("echo hello")

    def test_REGR_2_3__deploy_can_be_retried_after_failure(
        self, deployer: DockerDeployer, host_temp_dir: str
    ):
        marker = os.path.join(host_temp_dir, "marker.txt")
        with open(marker, "w") as f:
            f.write("retry-ok")

        node = deployer.node_from_config(name="node", config=_node_config())

        with pytest.raises(docker_exceptions.DockerDeployError):
            node.deploy(bind_mount_configs=self._duplicate_mounts(host_temp_dir))

        # повторный deploy с корректными опциями проходит и использует именно их
        node.deploy(
            bind_mount_configs=[
                BindMountConfig(
                    host_mnt=BindMount(src=host_temp_dir), dst=CONTAINER_MOUNT_DIR
                )
            ]
        )
        assert node.state is EntityState.DEPLOYED

        node.start()

        result = node.exec(f"cat {CONTAINER_MOUNT_DIR}/marker.txt")

        assert check_exit_code(result, 0, True)
        assert result is not None and "retry-ok" in result.stdout

    def test_REGR_2_4__failed_deploy_leaves_no_container_and_no_image_after_destroy(
        self, deployer: DockerDeployer, host_temp_dir: str
    ):
        node = deployer.node_from_config(name="node", config=_node_config())

        with pytest.raises(docker_exceptions.DockerDeployError):
            node.deploy(bind_mount_configs=self._duplicate_mounts(host_temp_dir))

        client = docker.from_env()
        try:
            assert not _container_exists(client, node.real_name)

            deployer.destroy_infra()

            assert node.state is EntityState.REMOVED
            assert not _container_exists(client, node.real_name)
            assert _images_with_prefix(client, node.real_name) == []
        finally:
            client.close()


# ----- пункт 3: освобождение адресов


@skip_if_no_docker
class TestAddressRelease:

    @staticmethod
    def _connected_node(
        deployer: DockerDeployer,
        ipv4_subnet: ipaddress.IPv4Network,
        name: str = "node_a",
    ):
        net = deployer.network_from_config(
            name="net", config=NetConfig(DockerNetworkConfigOptions(internal=False))
        )
        node = deployer.node_from_config(name=name, config=_node_config())
        (static_ip,) = _free_hosts(ipv4_subnet, 1)

        node.deploy()
        _deploy_net(net, ipv4_subnet)
        node.start()
        net.connect(node=node, subnet_label="1", addr=static_ip)

        return net, node, static_ip

    def test_REGR_3_1__undeploy_frees_the_address(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        net, a, static_ip = self._connected_node(deployer, ipv4_subnet)

        a.stop(0)
        a.undeploy()

        b = deployer.node_from_config(name="node_b", config=_node_config())
        b.deploy()
        b.start()

        net.connect(node=b, subnet_label="1", addr=static_ip)

        assert net.get_node_connection_info(node=b).addr == static_ip

    def test_REGR_3_2__remove_frees_the_address(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        net, a, static_ip = self._connected_node(deployer, ipv4_subnet)

        a.remove()

        b = deployer.node_from_config(name="node_b", config=_node_config())
        b.deploy()
        b.start()

        net.connect(node=b, subnet_label="1", addr=static_ip)

        assert net.get_node_connection_info(node=b).addr == static_ip

    def test_REGR_3_3__undeployed_node_has_no_connection_and_can_reconnect(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        # Следствие пункта 3: освободить адрес мало, сеть не должна продолжать
        # считать узел подключённым.
        net, node, static_ip = self._connected_node(deployer, ipv4_subnet)

        node.stop(0)
        node.undeploy()

        with pytest.raises(docker_exceptions.GetContainerIpError):
            net.get_node_connection_info(node=node)

        node.deploy()
        node.start()
        net.connect(node=node, subnet_label="1", addr=static_ip)

        assert net.get_node_connection_info(node=node).addr == static_ip

    def test_REGR_3_4__destroy_infra_with_connected_nodes_is_clean(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        net, a, _ = self._connected_node(deployer, ipv4_subnet)

        b = deployer.node_from_config(name="node_b", config=_node_config())
        b.deploy()
        b.start()
        net.connect(node=b, subnet_label="1")

        deployer.destroy_infra()

        assert a.state is EntityState.REMOVED
        assert b.state is EntityState.REMOVED
        assert net.state is EntityState.REMOVED
        assert len(deployer.nodes) == 0


# ----- пункт 4: make_snapshot


@skip_if_no_docker
class TestSnapshotStoppedNodes:

    @staticmethod
    def _started_nodes(deployer: DockerDeployer, count: int = 2):
        nodes = [
            deployer.node_from_config(name=f"node_{i}", config=_node_config())
            for i in range(count)
        ]
        for node in nodes:
            node.deploy()
            node.start()
        return nodes

    @staticmethod
    def _names(desc: SnapshotDescription) -> list[str]:
        with tarfile.open(desc.path, "r:gz") as tar:
            return tar.getnames()

    def test_REGR_4_1__offline_snapshot_when_all_nodes_are_stopped(
        self, deployer: DockerDeployer, snapshot_name: str
    ):
        nodes = self._started_nodes(deployer, count=2)
        for node in nodes:
            node.stop(1)

        desc = deployer.make_snapshot(snapshot_name=snapshot_name, online=False)

        assert desc.name == snapshot_name
        assert os.path.exists(desc.path)

        names = self._names(desc)
        assert "meta.json" in names
        for node in nodes:
            assert f"nodes/{node.uuid}.json" in names
            assert f"nodes/{node.uuid}.tar" in names

        # узлы, остановленные до снапшота, после него остаются остановленными
        for node in nodes:
            with pytest.raises(docker_exceptions.ExecOnContainerError):
                node.exec("true")

    def test_REGR_4_2__snapshot_of_empty_infrastructure(
        self, deployer: DockerDeployer, snapshot_name: str
    ):
        # Предполагается, что снапшот пустой инфраструктуры - допустимая
        # операция, а не ошибка.
        desc = deployer.make_snapshot(snapshot_name=snapshot_name)

        assert os.path.exists(desc.path)

        names = self._names(desc)
        assert "meta.json" in names
        assert not any(n.startswith("nodes/") for n in names)

    def test_REGR_4_3__offline_snapshot_with_running_and_stopped_nodes(
        self, deployer: DockerDeployer, snapshot_name: str
    ):
        running, stopped = self._started_nodes(deployer, count=2)
        stopped.stop(1)

        desc = deployer.make_snapshot(snapshot_name=snapshot_name, online=False)

        assert os.path.exists(desc.path)

        # запущенный узел после снапшота снова запущен, остановленный - нет
        assert check_exit_code(running.exec("echo ok"), 0, True)

        with pytest.raises(docker_exceptions.ExecOnContainerError):
            stopped.exec("true")

    def test_REGR_4_4__online_snapshot_when_all_nodes_are_stopped(
        self, deployer: DockerDeployer, snapshot_name: str
    ):
        nodes = self._started_nodes(deployer, count=2)
        for node in nodes:
            node.stop(1)

        desc = deployer.make_snapshot(snapshot_name=snapshot_name, online=True)

        assert os.path.exists(desc.path)

        names = self._names(desc)
        for node in nodes:
            assert f"nodes/{node.uuid}.tar" in names


# ----- пункт 5: node.update с неполным конфигом


@skip_if_no_docker
class TestNodeUpdatePartialConfig:
    # Что означает `None` в новом конфиге ("не менять" или "снять лимит"), в
    # issue не сказано, поэтому тесты проверяют только то, что ЗАДАНО в новом
    # конфиге, и что узел после update остаётся работоспособным.

    @staticmethod
    def _running_node(deployer: DockerDeployer):
        node = deployer.node_from_config(name="node", config=_node_config())
        node.deploy()
        node.start()
        return node

    def test_REGR_5_1__update_without_cpu_limit_applies_memory(
        self, deployer: DockerDeployer
    ):
        node = self._running_node(deployer)

        node.update(NodeConfig(base_image="alpine", mem_limit="512m"))

        assert _host_config(node.real_name)["Memory"] == 512 * 1024 * 1024
        assert check_exit_code(node.exec("echo ok"), 0, True)

    def test_REGR_5_2__update_without_mem_limit_applies_cpu(
        self, deployer: DockerDeployer
    ):
        node = self._running_node(deployer)

        node.update(NodeConfig(base_image="alpine", cpu_limit=2))

        host_config = _host_config(node.real_name)
        assert host_config["CpuPeriod"] == 100000
        assert host_config["CpuQuota"] == 200000
        assert check_exit_code(node.exec("echo ok"), 0, True)

    def test_REGR_5_3__update_without_any_limits_does_not_raise(
        self, deployer: DockerDeployer
    ):
        node = self._running_node(deployer)

        node.update(NodeConfig(base_image="alpine"))

        assert node.state is EntityState.DEPLOYED
        assert check_exit_code(node.exec("echo ok"), 0, True)
