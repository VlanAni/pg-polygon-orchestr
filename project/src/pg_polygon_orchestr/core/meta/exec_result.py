from dataclasses import dataclass


@dataclass(frozen=True)
class ExecResult:
    """Результат выполнения команды

    `exit_code`: `int | None` - результат исполнения команды\n
    `stdout`: `str` - стандартный поток вывода команды\n
    `stderr`: `str` - стандартный поток ошибок\n
    `execution_time`: `int` - время исполнения команды в наносекундах

    """

    exit_code: int | None
    stdout: str
    stderr: str
    execution_time: int  # nanoseconds
