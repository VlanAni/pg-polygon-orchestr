class NodeWithThatNameAlreadyExistsException(Exception):
    pass


class ThereIsNoDataForThisKeyException(Exception):
    pass


class NetConfigIncludeNotConfiguredNodeException(Exception):
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
