from abc import ABC

import typing
import inspect


class EasyDecodable(ABC):

    @classmethod
    def from_dict(cls, data: typing.Mapping[str, typing.Any]) -> typing.Self:
        values = {
            field: data[field] for field in inspect.signature(cls).parameters.keys()
        }

        return cls(**values)
