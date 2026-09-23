from dataclasses import dataclass

from ..serializable import Serializable, EasyDecodable


@dataclass(frozen=True)
class DockerNetworkConfigOptions(Serializable, EasyDecodable):

    internal: bool = False
    driver: str = "bridge"
