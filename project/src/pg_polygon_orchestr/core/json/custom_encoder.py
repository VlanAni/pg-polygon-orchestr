from json import JSONEncoder
import typing
from uuid import UUID
import enum

from ..abstract import Entity, Deployer
from ..serializable import Serializable


class CustomEncoder(JSONEncoder):
    def default(self, o: typing.Any) -> typing.Any:
        if isinstance(o, Entity):
            return o.transform_to_mapping()

        if isinstance(o, Deployer):
            return o.transform_to_mapping()

        if isinstance(o, UUID):
            return str(o)

        if isinstance(o, Serializable):
            return o.serialize()

        if isinstance(o, enum.Enum):
            return o.name

        return super().default(o=o)
