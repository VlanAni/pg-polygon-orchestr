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


class FailedToExecuteCommand(Exception):
    pass


# ----- DEPLOYER


class CannotDeployNodeException(Exception):
    pass


class CannotDeployInfra(Exception):
    pass


# ----- NODE_LINK


class NodeIsNotDeployer(Exception):
    pass


class FailedToStartNode(Exception):
    pass


class FailedToStopNode(Exception):
    pass


class FailedToExecCommand(Exception):
    pass


class FailedToUpdateConfiguration(Exception):
    pass


class FailedToGetIP(Exception):
    pass
