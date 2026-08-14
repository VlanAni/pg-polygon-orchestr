from . import common_exceptions

# ------ DEPLOYING ERRORS


class DockerClearError(common_exceptions.ClearError):
    pass


class DockerDeployError(common_exceptions.DeployError):
    pass


class DockerRemoveError(common_exceptions.RemoveError):
    pass


# ------ NETWORK ERROR


class ConnectToDockerNetError(common_exceptions.ConnectToNetError):
    pass


class DisconnectFromDockerNetError(common_exceptions.DisconnectFromNetError):
    pass


class GetDockerNetIpError(common_exceptions.GetNetIpError):
    pass


class GetContainerIpError(common_exceptions.GetNodeIpError):
    pass


# ------ CONTAINER ERRORS


class DockerContStartError(common_exceptions.StartNodeError):
    pass


class DockerContStopError(common_exceptions.StopNodeError):
    pass


class ExecOnContainerError(common_exceptions.ExecCommandError):
    pass


class UpdateContainerConfError(common_exceptions.UpdateConfError):
    pass


class ContainerAlreadyRunning(Exception):
    pass


class ContainerAlreadyStopped(Exception):
    pass


class ContainerDoesNotExist(Exception):
    pass


class FailedToCommit(Exception):
    pass


# ------ ОШИБКИ ВНУТРЕННЕЙ РАБОТЫ ДЕЛПОЕРА


class ImageBuildError(Exception):
    pass


class ResourceCreationError(Exception):
    pass


class FailedToDeleteAnImage(Exception):
    pass


class FailedToRestartContainersAfterFailedSnapshot(Exception):
    pass


class FailedToRestartContainersAfterSuccessSnapshot(Exception):
    pass


class FailedToSaveImageIntoTar(Exception):
    pass


class FailedToRestartContainers(Exception):
    pass


class FailedToRestartNodesAfterFailedFreezing(Exception):
    pass


# ------ SNAPSHOTS


class FailedToBuildDockerInsfrastructure(Exception):
    pass


class FailedToBuildDockerVolume(Exception):
    pass


class FailedToRemoveInfrastructureAfterFailedBuild(Exception):
    pass


class FailedToBuildDockerNode(Exception):
    pass


class FailedToBuildDockerNetwork(Exception):
    pass
