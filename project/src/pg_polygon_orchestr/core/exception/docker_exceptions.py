# ----- DOCKER_DEPLOYER


class DeploymentError(Exception):
    pass


class ImageBuildError(Exception):
    pass


class DockerConnectionError(Exception):
    pass


class CreateNetworkError(Exception):
    pass


# исключения приватной функции создания сетей


class CannotCreateDockerNetwork(Exception):
    pass


# ислючения функции destroy_everything


class CannotDestroyTheNodeException(Exception):
    pass


class CannotDestroyTheImageException(Exception):
    pass


class CannotDestroyTheNetwork(Exception):
    pass


# ----- DOCKER_NODE


# исключения которые выбрасывают функции уровня DockerNode
class DisonnectFunctionError(Exception):
    pass


class DockerNodeAPIErrorOrccursException(Exception):
    pass


class ConnectFunctionError(Exception):
    pass


class CannotExecACommandOnNotRunningContainer(Exception):
    pass


class CannotFindImageToRunAContainer(Exception):
    pass


class ContainerErrorDuringRunning(Exception):
    pass


class NoDockerContainerToPerformOperation(Exception):
    pass


# Исключения принадлежащие приватным функциям подключения и отсоединения
class CannotConnectToTheNetwork(Exception):
    pass


class CannotDisconnectFromTheNetwork(Exception):
    pass


# исключения специфичные для Update() у DockerNode
class UpdateConfigurationCannotBePerfomedIfCpuLimitNotPositive(Exception):
    pass


# ----- DOCKER_INFRASTRUCTURE
