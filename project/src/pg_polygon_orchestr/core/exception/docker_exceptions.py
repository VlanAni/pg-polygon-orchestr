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


class ContainerUnexpectedlyRunning(common_exceptions.StartNodeError):
    pass


class ContainerUnexpectedlyStopped(common_exceptions.StopNodeError):
    pass


# ------ ОШИБКИ ВНУТРЕННЕЙ РАБОТЫ ДЕЛПОЕРА


class ImageBuildError(Exception):
    pass


class ResourceCreationError(Exception):
    pass


class FailedToDeleteAnImage(Exception):
    pass
