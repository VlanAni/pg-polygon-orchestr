from enum import Enum


class DeployerAction(Enum):
    MAKE_SNAPSHOT = 1
    REMOVE_INFRASTRUCTURE = 3
    PUT_NODE_CONFIG = 4
    PUT_VOLUME_CONFIG = 5
    PUT_NETWORK_CONFIG = 6
