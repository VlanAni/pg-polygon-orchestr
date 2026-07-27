class DeploymentError(Exception):
    """the base class for all node building exceptions"""


class ImageBuildError(DeploymentError):
    """
    cannot build an image from the Dockerfile
    """


class DockerConnectionError(DeploymentError):
    """
    cannot connect to the docker server
    """
