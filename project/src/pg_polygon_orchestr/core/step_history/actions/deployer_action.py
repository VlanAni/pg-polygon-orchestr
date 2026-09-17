from .action import Action


class DeployerAction(Action):
    MAKE_SNAPSHOT = 1
    REMOVE_INFRASTRUCTURE = 3
    PUT_NODE_CONFIG = 4
    PUT_VOLUME_CONFIG = 5
    PUT_NETWORK_CONFIG = 6
