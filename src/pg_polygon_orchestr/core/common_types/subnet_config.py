import ipaddress


class SubnetConfig:

    def __init__(
        self,
        label: str,
        subnet: str | ipaddress.IPv4Network,
        gateway: str | ipaddress.IPv4Address,
    ):
        if isinstance(subnet, str):
            try:
                self.__subnet = ipaddress.IPv4Network(address=subnet)
            except Exception as err:
                raise SubnetConfigFormatError(
                    f"failed to extract IP-network from the address {subnet}"
                ) from err
        else:
            self.__subnet = subnet

        if isinstance(gateway, str):
            try:
                self.__gateway = ipaddress.IPv4Address(address=gateway)
            except Exception as err:
                raise SubnetConfigFormatError(
                    f"failed to extract the gateway from the address {gateway}"
                ) from err
        else:
            self.__gateway = gateway

        self.__label = label

    @property
    def label(self) -> str:
        return self.__label

    @property
    def subnet(self) -> ipaddress.IPv4Network:
        return self.__subnet

    @property
    def gateway(self) -> ipaddress.IPv4Address:
        return self.__gateway


class SubnetConfigFormatError(Exception):
    pass
