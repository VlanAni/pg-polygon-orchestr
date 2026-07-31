class NodeWithThatNameAlreadyExistsException(Exception):
    pass


class ThereIsNoDataForThisKeyException(Exception):
    pass


class NetConfigIncludeNotConfiguredNodeException(Exception):
    pass


class DockerVolumeConfigIncludeNotConfiguredNode(Exception):
    pass


# ----- INFRA


class FailedToStartNodeFromInfrastructureException(Exception):
    pass


class FailedToStopInfrastructure(Exception):
    pass


class FailedToFindANodeWithByItsName(Exception):
    pass


class FailedToUpdateConfiguration(Exception):
    pass


class FailedToExecuteCommand(Exception):
    pass


# ----- DEPLOYER


class CannotDeployNodeException(Exception):
    pass


class CannotDeployInfra(Exception):
    pass


# -----
