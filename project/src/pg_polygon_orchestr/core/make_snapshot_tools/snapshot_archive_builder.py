import uuid
import tarfile
import pathlib
import os
import typing
import json
import io

from ..exception import common_exceptions
from ..json import CustomEncoder


class SnapshotArchiveBuilder:

    __snapshots_dir = os.path.join(
        pathlib.Path.home(), ".pg-polygon-orchestr", "snapshots"
    )
    __snapshot_format = ".tar.gz"

    def __init__(self, archive_name: uuid.UUID | str) -> None:
        self.__tar_obj: tarfile.TarFile | None = None
        self.__path = self.__snapshot_full_path(archive_name=archive_name)

    def __enter__(self) -> SnapshotArchiveBuilder:
        os.makedirs(name=self.__snapshots_dir, exist_ok=True)

        self.__tar_obj = tarfile.open(name=self.__path, mode="w:gz")

        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore
        if self.__tar_obj is not None:
            self.__tar_obj.close()
            self.__tar_obj = None

    def __snapshot_full_path(self, archive_name: uuid.UUID | str) -> str:
        return os.path.join(
            self.__snapshots_dir, f"{str(archive_name)}{self.__snapshot_format}"
        )

    # ----- public methods

    def add_json_object_info(self, tag: str, obj: typing.Any):
        if self.__tar_obj is None:
            raise common_exceptions.MakeSnapshotError(f"the snapshoter is not opened")

        try:
            json_dump = json.dumps(
                obj=obj, cls=CustomEncoder, indent=4, ensure_ascii=False
            ).encode("utf-8")
        except Exception as err:
            raise common_exceptions.MakeSnapshotError(
                f"failed to serialize passed object"
            ) from err

        tarInfo = tarfile.TarInfo(name=tag)

        tarInfo.size = len(json_dump)

        try:
            self.__tar_obj.addfile(
                tarinfo=tarInfo, fileobj=io.BytesIO(initial_bytes=json_dump)
            )
        except Exception as err:
            raise common_exceptions.MakeSnapshotError(
                f"failed to put .json into .tar archive"
            ) from err

    def get_snapshot_dir_path(self) -> str:
        return self.__snapshots_dir

    def put_tar_file_into_snapshot(self, tag: str, path: str, size: int) -> None:
        if self.__tar_obj is None:
            raise common_exceptions.MakeSnapshotError(f"the snapshoter is not opened")

        try:
            f = open(path, "rb")
        except OSError as err:
            raise common_exceptions.MakeSnapshotError(
                f"failed to open tar file for reading"
            ) from err

        info = tarfile.TarInfo(name=tag)
        info.size = size

        try:
            self.__tar_obj.addfile(tarinfo=info, fileobj=f)
        except Exception as err:
            raise common_exceptions.MakeSnapshotError(
                f"failed to put .tar into .tar archive"
            ) from err
        finally:
            f.close()

    def destroy_tar(self) -> None:
        if self.__tar_obj is not None:
            self.__tar_obj.close()

        os.remove(path=self.__path)

        self.__tar_obj = None
