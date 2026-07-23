from abc import ABC, abstractmethod


class Infrastructure(ABC):

    @abstractmethod
    def run(self) -> bool:
        pass

    @abstractmethod
    def freeze(self, timeout: int) -> bool:
        pass
