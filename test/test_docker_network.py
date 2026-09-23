import docker
import pytest
import ipaddress

from pg_polygon_orchestr import NodeConfig
from pg_polygon_orchestr import NetConfig
from pg_polygon_orchestr import DockerDeployer
from pg_polygon_orchestr import DockerNodeConfigOptions
from pg_polygon_orchestr import DockerNetworkConfigOptions
from pg_polygon_orchestr import common_exceptions
from pg_polygon_orchestr import SubnetConfig

from .fixtures import deployer
from .fixtures import ipv4_subnet
from .fixtures import generate_private_subnets
from .fixtures import check_exit_code

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
class TestDockerNetwork:

    def test_NET_1__internal_network_with_two_containers(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        config = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine",
            docker_params=DockerNodeConfigOptions(detach_from_default_bridge=True),
        )

        a = deployer.put_node_config(name="node_a", config=config)
        b = deployer.put_node_config(name="node_b", config=config)

        assert a and b

        for node in [a, b]:
            node.deploy()

        net_config = NetConfig(
            DockerNetworkConfigOptions(internal=True),
        )

        net = deployer.put_network_config(name="net", config=net_config)

        with pytest.raises(common_exceptions.EntityIsNotDeployed):
            net.connect(node=a, subnet_label="placeholder")

        a.start()
        b.start()

        subnet_hosts_iter = ipv4_subnet.hosts()
        gateway = next(subnet_hosts_iter)

        net.deploy(
            subnet_configs=[
                SubnetConfig(label="1", subnet=ipv4_subnet, gateway=gateway)
            ]
        )

        net.connect(node=a, subnet_label=net.subnets()[0].label)
        net.connect(node=b, subnet_label=net.subnets()[0].label)

        a_ping_b_result = a.exec(f"ping -c 1 {b.real_name}")
        assert check_exit_code(a_ping_b_result, 0, True)

        b_ping_a_result = b.exec(f"ping -c 1 {a.real_name}")
        assert check_exit_code(b_ping_a_result, 0, True)

        a_ping_google = a.exec("ping -c 3 8.8.8.8")
        b_ping_google = b.exec("ping -c 3 8.8.8.8")

        assert check_exit_code(a_ping_google, 0, False)
        assert check_exit_code(b_ping_google, 0, False)

        net.disconnect(node=a)

        a_ping_b_after_disconnect = a.exec(f"ping -c 1 {b.real_name}")
        assert check_exit_code(a_ping_b_after_disconnect, 0, False)

        net.disconnect(node=b)

    def test_NET_2__public_network_with_three_containers(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        config = NodeConfig(
            cpu_limit=1,
            mem_limit="512m",
            os="alpine:latest",
            docker_params=DockerNodeConfigOptions(detach_from_default_bridge=True),
        )

        a = deployer.put_node_config(name="node_a", config=config)
        b = deployer.put_node_config(name="node_b", config=config)
        c = deployer.put_node_config(name="node_c", config=config)

        net_config = NetConfig(DockerNetworkConfigOptions(internal=False))

        net = deployer.put_network_config(name="net", config=net_config)

        for node in [a, b, c]:
            node.deploy()
            node.start()

        hosts = ipv4_subnet.hosts()
        gateway = next(hosts)

        net.deploy(
            subnet_configs=[
                SubnetConfig(label="1", subnet=ipv4_subnet, gateway=gateway)
            ]
        )

        net.connect(node=a, subnet_label=net.subnets()[0].label)
        net.connect(node=b, subnet_label=net.subnets()[0].label)
        net.connect(node=c, subnet_label=net.subnets()[0].label)

        a_ping_b = a.exec(f"ping -c 1 {b.real_name}")
        a_ping_c = a.exec(f"ping -c 1 {c.real_name}")
        b_ping_a = b.exec(f"ping -c 1 {a.real_name}")
        b_ping_c = b.exec(f"ping -c 1 {c.real_name}")
        c_ping_a = c.exec(f"ping -c 1 {a.real_name}")
        c_ping_b = c.exec(f"ping -c 1 {b.real_name}")

        assert check_exit_code(a_ping_b, 0, True)
        assert check_exit_code(a_ping_c, 0, True)
        assert check_exit_code(b_ping_a, 0, True)
        assert check_exit_code(b_ping_c, 0, True)
        assert check_exit_code(c_ping_a, 0, True)
        assert check_exit_code(c_ping_b, 0, True)

        a_ping_google = a.exec("ping -c 3 8.8.8.8")

        assert check_exit_code(a_ping_google, 0, True)

    def test_NET_3__four_nodes_and_four_networks(self, deployer: DockerDeployer):
        config = NodeConfig(
            cpu_limit=1,
            mem_limit="512m",
            os="ubuntu:latest",
            docker_params=DockerNodeConfigOptions(
                cap_add=["NET_ADMIN"],
                detach_from_default_bridge=True,
                sysctls={"net.ipv4.ip_forward": "1"},
            ),
        )

        a = deployer.put_node_config(name="node_a", config=config)
        b = deployer.put_node_config(name="node_b", config=config)
        c = deployer.put_node_config(name="node_c", config=config)
        d = deployer.put_node_config(name="node_d", config=config)

        net_config = NetConfig(DockerNetworkConfigOptions(internal=False))

        net1 = deployer.put_network_config(name="net1", config=net_config)
        net2 = deployer.put_network_config(name="net2", config=net_config)
        net3 = deployer.put_network_config(name="net3", config=net_config)
        net4 = deployer.put_network_config(name="net4", config=net_config)

        subnets = generate_private_subnets(count=4)
        gateways = [next(subnet.hosts()) for subnet in subnets]
        docker_nets = [net1, net2, net3, net4]

        for i in range(len(subnets)):
            docker_nets[i].deploy(
                subnet_configs=[
                    SubnetConfig(label="1", subnet=subnets[i], gateway=gateways[i])
                ]
            )

        routes = [
            (a, c, b, net1, net2),
            (b, d, c, net2, net3),
            (c, a, d, net3, net4),
            (d, b, a, net4, net1),
        ]

        for node in [a, b, c, d]:
            node.deploy()

        a.start()
        b.start()
        c.start()
        d.start()

        net1.connect(node=a, subnet_label=net1.subnets()[0].label)
        net1.connect(node=b, subnet_label=net1.subnets()[0].label)

        net2.connect(node=b, subnet_label=net2.subnets()[0].label)
        net2.connect(node=c, subnet_label=net2.subnets()[0].label)

        net3.connect(node=c, subnet_label=net3.subnets()[0].label)
        net3.connect(node=d, subnet_label=net3.subnets()[0].label)

        net4.connect(node=a, subnet_label=net4.subnets()[0].label)
        net4.connect(node=d, subnet_label=net4.subnets()[0].label)

        for node in [a, b, c, d]:
            node.exec(
                "sh -c 'apt-get update -qq && apt-get install -y iproute2 iputils-ping traceroute'"
            )

        for source, target, middle_node, source_net, target_net in routes:
            target_ip = target_net.get_node_connection_info(node=target).addr
            middle_node_source_net_ip = source_net.get_node_connection_info(
                node=middle_node
            ).addr
            middle_node_target_net_ip = target_net.get_node_connection_info(
                node=middle_node
            ).addr
            target_net_addr = target_net.subnets()[0].subnet
            source_net_addr = source_net.subnets()[0].subnet

            from_src_to_target = source.exec(
                f"ip route add {target_net_addr} via {middle_node_source_net_ip}"
            )

            from_target_to_src = target.exec(
                f"ip route add {source_net_addr} via {middle_node_target_net_ip}"
            )

            assert check_exit_code(from_src_to_target, 0, True)
            assert check_exit_code(from_target_to_src, 0, True)

            ping_result = source.exec(f"ping -c 1 {target_ip}")
            assert check_exit_code(ping_result, 0, True)

            traceroute_result = source.exec(f"traceroute -n {target_ip}")
            assert check_exit_code(traceroute_result, 0, True)
            assert str(middle_node_source_net_ip) in traceroute_result.stdout  # type: ignore

    def test_NET_4__two_internal_networks_and_switch(self, deployer: DockerDeployer):
        node_config = NodeConfig(
            os="alpine",
            cpu_limit=1,
            mem_limit="256m",
            docker_params=DockerNodeConfigOptions(
                cap_add=["NET_ADMIN"], detach_from_default_bridge=True
            ),
        )

        switch_config = NodeConfig(
            os="alpine",
            cpu_limit=1,
            mem_limit="256m",
            docker_params=DockerNodeConfigOptions(
                cap_add=["NET_ADMIN"],
                detach_from_default_bridge=True,
                sysctls={"net.ipv4.ip_forward": "1"},
            ),
        )

        net_config = NetConfig(DockerNetworkConfigOptions(internal=False))

        a = deployer.put_node_config(name="node_a", config=node_config)
        b = deployer.put_node_config(name="node_b", config=node_config)
        c = deployer.put_node_config(name="node_c", config=node_config)
        d = deployer.put_node_config(name="node_d", config=node_config)
        switch = deployer.put_node_config(name="switch", config=switch_config)

        for node in [a, b, c, d, switch]:
            node.deploy()

        net1 = deployer.put_network_config(name="net_1", config=net_config)
        net2 = deployer.put_network_config(name="net_2", config=net_config)

        subnets = generate_private_subnets(count=2)
        gateways = [next(subnet.hosts()) for subnet in subnets]

        net1.deploy(
            subnet_configs=[
                SubnetConfig(label="1", subnet=subnets[0], gateway=gateways[0])
            ]
        )
        net2.deploy(
            subnet_configs=[
                SubnetConfig(label="1", subnet=subnets[1], gateway=gateways[1])
            ]
        )

        a.start()
        b.start()
        c.start()
        d.start()

        net1.connect(node=a, subnet_label=net1.subnets()[0].label)
        net1.connect(node=b, subnet_label=net1.subnets()[0].label)

        net2.connect(node=c, subnet_label=net2.subnets()[0].label)
        net2.connect(node=d, subnet_label=net2.subnets()[0].label)

        switch.start()

        net1.connect(node=switch, subnet_label=net1.subnets()[0].label)
        net2.connect(node=switch, subnet_label=net2.subnets()[0].label)

        a_ip = net1.get_node_connection_info(node=a).addr
        b_ip = net1.get_node_connection_info(node=b).addr
        c_ip = net2.get_node_connection_info(node=c).addr
        d_ip = net2.get_node_connection_info(node=d).addr
        switch_net1_ip = net1.get_node_connection_info(node=switch).addr
        switch_net2_ip = net2.get_node_connection_info(node=switch).addr
        net1_ip = net1.subnets()[0].subnet
        net2_ip = net2.subnets()[0].subnet

        for node_net_1 in [a, b]:
            net_2_route = node_net_1.exec(
                f"ip route add {net2_ip} via {switch_net1_ip}"
            )

            assert check_exit_code(net_2_route, 0, True)

        for node_net_2 in [c, d]:
            net_1_route = node_net_2.exec(
                f"ip route add {net1_ip} via {switch_net2_ip}"
            )

            assert check_exit_code(net_1_route, 0, True)

        a_ping_b = a.exec(f"ping -c 1 {b.real_name}")
        b_ping_a = b.exec(f"ping -c 1 {a.real_name}")

        assert check_exit_code(a_ping_b, 0, True)
        assert check_exit_code(b_ping_a, 0, True)

        c_ping_d = c.exec(f"ping -c 1 {d.real_name}")
        d_ping_c = d.exec(f"ping -c 1 {c.real_name}")

        assert check_exit_code(c_ping_d, 0, True)
        assert check_exit_code(d_ping_c, 0, True)

        for net1_node in [a, b]:
            ping_c = net1_node.exec(f"ping -c 1 {c_ip}")

            assert check_exit_code(ping_c, 0, True)

            ping_d = net1_node.exec(f"ping -c 1 {d_ip}")

            assert check_exit_code(ping_d, 0, True)

        for net2_node in [c, d]:
            ping_a = net2_node.exec(f"ping -c 1 {a_ip}")

            assert check_exit_code(ping_a, 0, True)

            ping_b = net2_node.exec(f"ping -c 1 {b_ip}")

            assert check_exit_code(ping_b, 0, True)

    def test_NET_5__network_ipv4_only_assigns_ipv4_addresses(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        node_config = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine",
            docker_params=DockerNodeConfigOptions(detach_from_default_bridge=True),
        )
        net_config = NetConfig(DockerNetworkConfigOptions(internal=False))

        a = deployer.put_node_config(name="node_a", config=node_config)
        net = deployer.put_network_config(name="net", config=net_config)

        a.deploy()
        a.start()

        net.deploy(
            subnet_configs=[
                SubnetConfig(
                    label="1", subnet=ipv4_subnet, gateway=next(ipv4_subnet.hosts())
                )
            ]
        )
        net.connect(node=a, subnet_label=net.subnets()[0].label)

        ipv4_addr = net.get_node_connection_info(node=a).addr
        assert ipv4_addr

        client = docker.from_env()
        try:
            container = client.containers.get(container_id=a.real_name)
            net_settings = container.attrs["NetworkSettings"]["Networks"][net.real_name]
            assert net_settings["IPAddress"] == str(ipv4_addr)
            assert not net_settings.get("GlobalIPv6Address")
        finally:
            client.close()

    def test_NET_6__node_gets_requested_static_ipv4(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        node_config = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine",
            docker_params=DockerNodeConfigOptions(detach_from_default_bridge=True),
        )
        net_config = NetConfig(DockerNetworkConfigOptions(internal=True))

        node = deployer.put_node_config(name="node", config=node_config)
        net = deployer.put_network_config(name="net", config=net_config)

        hosts = ipv4_subnet.hosts()
        gateway = next(hosts)
        static_ip = gateway

        for _ in range(5):
            static_ip = next(hosts)

        node.deploy()
        net.deploy(
            subnet_configs=[
                SubnetConfig(label="1", subnet=str(ipv4_subnet), gateway=gateway)
            ]
        )

        node.start()
        net.connect(node=node, subnet_label=net.subnets()[0].label, addr=static_ip)

        assigned_ip = net.get_node_connection_info(node=node).addr
        assert assigned_ip == static_ip

    def test_NET_7__two_nodes_with_static_ipv4_no_conflict_and_can_communicate(
        self, deployer: DockerDeployer, ipv4_subnet: ipaddress.IPv4Network
    ):
        node_config = NodeConfig(
            cpu_limit=1,
            mem_limit="256m",
            os="alpine",
            docker_params=DockerNodeConfigOptions(detach_from_default_bridge=True),
        )
        net_config = NetConfig(DockerNetworkConfigOptions(internal=False))

        a = deployer.put_node_config(name="node_a", config=node_config)
        b = deployer.put_node_config(name="node_b", config=node_config)
        net = deployer.put_network_config(name="net", config=net_config)

        hosts = ipv4_subnet.hosts()
        gateway = next(hosts)
        a_ip = next(hosts)
        b_ip = next(hosts)

        for _ in range(15):
            b_ip = next(hosts)

        a.deploy()
        b.deploy()
        net.deploy(
            subnet_configs=[
                SubnetConfig(label="1", subnet=ipv4_subnet, gateway=gateway)
            ]
        )

        a.start()
        b.start()

        net.connect(node=a, subnet_label=net.subnets()[0].label, addr=a_ip)
        net.connect(node=b, subnet_label=net.subnets()[0].label, addr=b_ip)

        assert net.get_node_connection_info(node=a).addr == a_ip
        assert net.get_node_connection_info(node=b).addr == b_ip

        ping_a_to_b = a.exec(f"ping -c 1 {b_ip}")
        ping_b_to_a = b.exec(f"ping -c 1 {a_ip}")

        assert check_exit_code(ping_a_to_b, 0, True)
        assert check_exit_code(ping_b_to_a, 0, True)
