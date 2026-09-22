from abc import ABC, abstractmethod
from uuid import UUID


class InfraObject(ABC):

    @property
    @abstractmethod
    def uuid(self) -> UUID:
        pass
