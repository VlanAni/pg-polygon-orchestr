from dataclasses import dataclass


@dataclass(frozen=True)
class ExecResult:
    exit_code: int | None
    stdout: str
    stderr: str
    execution_time: int  # nanoseconds
