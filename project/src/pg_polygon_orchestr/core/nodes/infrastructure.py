from abc import ABC, abstractmethod


class Infrastructure(ABC):

    @abstractmethod
    def get_network_ip_addr(self, net_name: str) -> str | None:
        pass

    @abstractmethod
    def is_alive(self) -> bool:
        pass
