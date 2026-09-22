import ipaddress
from typing import Any, Mapping

from .subnet_config import SubnetConfig
from ..serializable import Serializable


class SubnetDesc(Serializable):

    def __init__(self, config: SubnetConfig):
        self.__subnet: ipaddress.IPv4Network = config.subnet
        self.__gateway: ipaddress.IPv4Address = config.gateway
        self.__used_addresses: set[ipaddress.IPv4Address] = set(
            [self.__gateway, self.__subnet.broadcast_address]
        )

    def allocate_address(
        self, addr: ipaddress.IPv4Address | None = None
    ) -> ipaddress.IPv4Address:
        if addr:
            if addr in self.__subnet:
                if addr in self.__used_addresses:
                    raise AddressInUse(
                        f"the address {str(addr)} in the subnet {str(self.__subnet)} is already use"
                    )

                self.__used_addresses.add(addr)
                return addr
            else:
                raise NetworkDoesNotHaveThisAddress(
                    f"the subnet {str(self.__subnet)} does not have the address {str(addr)}"
                )

        for host_addr in self.__subnet.hosts():
            if not (host_addr in self.__used_addresses):
                self.__used_addresses.add(host_addr)
                return host_addr

        raise NoFreeAddressesInTheNetwork(
            f"the network {self.__subnet.network_address} does not have any free address"
        )

    def free_address(self, addr: ipaddress.IPv4Address) -> None:
        try:
            self.__used_addresses.remove(addr)
        except KeyError:
            pass

    def check_address_in_subnet(self, addr: ipaddress.IPv4Address) -> bool:
        return addr in self.__subnet

    @property
    def address(self) -> str:
        return self.__subnet.with_prefixlen

    @property
    def gateway(self) -> ipaddress.IPv4Address:
        return self.__gateway

    @property
    def subnet(self) -> ipaddress.IPv4Network:
        return self.__subnet

    def serialize(self) -> Mapping[str, Any]:
        return {"subnet": self.__subnet, "gateway": self.__gateway}


class NoFreeAddressesInTheNetwork(Exception):
    pass


class NetworkDoesNotHaveThisAddress(Exception):
    pass


class AddressInUse(Exception):
    pass
