import json

from .step import Step
from ..json import PgPolygonEncoder


class StepHistoryManager:

    def __init__(self, history_tag: str | None = None): ...

    def push(self, step: Step):
        json_dump = json.dumps(
            obj=step, cls=PgPolygonEncoder, indent=4, ensure_ascii=False
        ).encode("utf-8")

        ...
