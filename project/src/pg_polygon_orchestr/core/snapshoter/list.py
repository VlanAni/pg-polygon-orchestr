import os
import pathlib

from ..meta import SnapshotDescription


def list_snapshots() -> list[SnapshotDescription]:
    snapshot_dir = os.path.join(
        pathlib.Path.home(), ".pg-polygon-orchestr", "snapshots"
    )

    if not os.path.exists(path=snapshot_dir):
        return []

    snapshots_files = os.listdir(path=snapshot_dir)
    snapshots_descs: list[SnapshotDescription] = list()

    for file_name in snapshots_files:
        if file_name.endswith(".tar.gz"):
            snap_name = file_name.removesuffix(".tar.gz")
            snapshots_descs.append(SnapshotDescription(name=snap_name))

    return snapshots_descs


def find_snap_desc(target: str) -> SnapshotDescription | None:
    snapshot_dir = os.path.join(
        pathlib.Path.home(), ".pg-polygon-orchestr", "snapshots"
    )

    if not os.path.exists(path=snapshot_dir):
        return None

    snapshots_files = os.listdir(path=snapshot_dir)

    for file_name in snapshots_files:
        if file_name.endswith(".tar.gz"):
            snap_name = file_name.removesuffix(".tar.gz")
            if snap_name == target:
                return SnapshotDescription(name=snap_name)

    return None
