from .steps.step import Step


class StepHistoryManager:

    def __init__(self, history_tag: str | None = None): ...

    def push(self, step: Step): ...
