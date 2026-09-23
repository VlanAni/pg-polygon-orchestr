from abc import ABC

from dataclasses import fields

import typing


class Serializable(ABC):

    def serialize(self) -> typing.Mapping[str, typing.Any]:
        return {field.name: getattr(self, field.name) for field in fields(self)}  # type: ignore
