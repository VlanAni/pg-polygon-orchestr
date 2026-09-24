from dataclasses import dataclass


from ..serializable import Serializable, EasyDecodable


@dataclass(frozen=True)
class DockerBindMountOpts(Serializable, EasyDecodable):

    ro: bool = False
