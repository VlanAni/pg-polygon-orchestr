from abc import ABC, abstractmethod


class Infrastructure(ABC):

    @abstractmethod
    def start(self) -> bool:
        pass

    @abstractmethod
    def stop(self, timeout: int) -> bool:
        pass
