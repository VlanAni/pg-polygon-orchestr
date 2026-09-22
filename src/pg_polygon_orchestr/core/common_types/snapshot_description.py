import os
import pathlib
from dataclasses import dataclass


@dataclass(frozen=True)
class SnapshotDescription:
    name: str

    @property
    def path(self) -> str:
        return os.path.join(
            pathlib.Path.home(),
            ".pg-polygon-orchestr",
            "snapshots",
            f"{self.name}.tar.gz",
        )
