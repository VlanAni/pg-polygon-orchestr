import typing

from .step import Step
from .deployer_action import DeployerAction

from ..configs import Config
from ..configs import NetConfig, NodeConfig, VolumeConfig
from ..abstract import Deployer


class DeployerStep(Step):

    def __init__(
        self,
        action: DeployerAction,
        deployer: Deployer | None = None,
        snapshot_name: str = "",
        online: bool = False,
        name: str = "",
        config: Config | None = None,
    ):
        self.__deployer = deployer
        self.__action: DeployerAction = action
        match action:

            case DeployerAction.MAKE_SNAPSHOT:

                self.__args: dict[str, typing.Any] = {
                    "snapshot_name": snapshot_name,
                    "online": online,
                }
                return

            case DeployerAction.REMOVE_INFRASTRUCTURE:
                self.__args = {}
                return

            case DeployerAction.PUT_NETWORK_CONFIG if (not name) or (not config):

                if not isinstance(config, NetConfig):
                    raise KeyError(f"config must be of the type {type(NetConfig)}")

            case DeployerAction.PUT_NODE_CONFIG if (not name) or (not config):

                if not isinstance(config, NodeConfig):
                    raise KeyError(f"config must be of the type {type(NodeConfig)}")

            case DeployerAction.PUT_VOLUME_CONFIG if (not name) or (not config):

                if not isinstance(config, VolumeConfig):
                    raise KeyError(f"config must be of the type {type(VolumeConfig)}")

            case _:

                raise KeyError(
                    f"name and config params must be non-null for put_*_config function"
                )

        self.__args = {"name": name, "config": config}

    def perform(self) -> None | typing.Any:

        if self.__deployer is None:
            raise FailedPerformException(f"no specified deployer")

        match self.__action:

            case DeployerAction.MAKE_SNAPSHOT:

                try:
                    return self.__deployer.make_snapshot(**self.__args)
                except Exception as err:
                    raise FailedPerformException("failed to make snapshot") from err

            case DeployerAction.REMOVE_INFRASTRUCTURE:

                try:
                    self.__deployer.remove_infrastructure()
                except Exception as err:
                    raise FailedPerformException(
                        "failed to remove infrastructure"
                    ) from err

            case DeployerAction.PUT_NETWORK_CONFIG:

                try:
                    return self.__deployer.put_network_config(**self.__args)
                except Exception as err:
                    raise FailedPerformException(
                        "failed to put network config"
                    ) from err

            case DeployerAction.PUT_NODE_CONFIG:

                try:
                    return self.__deployer.put_node_config(**self.__args)
                except Exception as err:
                    raise FailedPerformException(f"failed to put node config") from err

            case DeployerAction.PUT_VOLUME_CONFIG:

                try:
                    return self.__deployer.put_node_config(**self.__args)
                except Exception as err:
                    raise FailedPerformException(
                        f"failed to put volume config"
                    ) from err

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        return super().serialize()


class FailedPerformException(Exception):
    pass
