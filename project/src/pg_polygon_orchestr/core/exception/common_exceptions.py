# ------ INFRASTRUCTURE MANAGING ERRORS


class DeployError(Exception):
    pass


class ClearError(Exception):
    pass


class RemoveError(Exception):
    pass


# ------ NETWORK ERRORS


class ConnectToNetError(Exception):
    pass


class DisconnectFromNetError(Exception):
    pass


class GetNetIpError(Exception):
    pass


class GetNodeIpError(Exception):
    pass


# ------ NODE ERRORS


class StartNodeError(Exception):
    pass


class ExecCommandError(Exception):
    pass


class UpdateConfError(Exception):
    pass


class StopNodeError(Exception):
    pass


# ------ SNAPSHOT ERRORS


class MakeSnapshotError(Exception):
    pass


class BuildFromSnapshotError(Exception):
    pass


class WriteStepError(Exception):
    pass


class BuildFromStepsError(Exception):
    pass


# ------ STATE CHECK ERRORS


class EntityIsRemovedException(Exception):
    pass


class EntityIsAlreadyDeployed(Exception):
    pass


class EntityIsNotDeployed(Exception):
    pass
