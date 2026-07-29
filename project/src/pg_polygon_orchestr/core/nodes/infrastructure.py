from abc import ABC, abstractmethod


class Infrastructure(ABC):

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self, timeout: int) -> None:
        pass
