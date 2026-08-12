import os
import docker.errors as dockerapi_errors
import docker.models.images as dockerapi_images
import typing

from ..exception import docker_exceptions


class ImageTarDescriptor:
    def __init__(self, path: str):
        self.__path = path
        self.__size = os.path.getsize(filename=path)

    def get_path(self) -> str:
        return self.__path

    def get_size(self) -> int:
        return self.__size


def save_image(
    image: dockerapi_images.Image, dir: str, tar_name: str
) -> ImageTarDescriptor:
    path = os.path.join(dir, f"{tar_name}.tar")

    try:
        f = open(path, "wb")
    except OSError as err:
        raise docker_exceptions.FailedToSaveImageIntoTar(
            f"failed to open .tar file {path}"
        ) from err

    try:
        for chunk in image.save():
            byte_chunk = typing.cast(bytes, chunk)
            byte_nums = len(byte_chunk)
            wrote = 0
            while wrote < byte_nums:
                wrote += f.write(byte_chunk[wrote:])

    except dockerapi_errors.APIError as err:
        os.remove(path=path)
        raise docker_exceptions.FailedToSaveImageIntoTar(
            f"failed to get a chunk of the image {image}"
        ) from err
    except BlockingIOError as err:
        os.remove(path=path)
        raise docker_exceptions.FailedToSaveImageIntoTar(
            f"failed to write a chunk into buffer"
        ) from err
    finally:
        f.close()

    return ImageTarDescriptor(path=path)
