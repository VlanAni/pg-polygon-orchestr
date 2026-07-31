# abstract class for deploying nodes using its config

from abc import ABC, abstractmethod

from ..configs.infra_config import InfConfig

from ..nodes.infrastructure import Infrastructure


class Deployer(ABC):

    @abstractmethod
    def destroy_everything(self) -> None:
        pass

    @abstractmethod
    def deploy_infrastructure(self, inf_config: InfConfig) -> Infrastructure:
        pass
