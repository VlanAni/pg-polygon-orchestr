class VolumeConfig:

    def __init__(
        self,
        name: str,
        owner_name: str,
        driver: str,
        delete_on_destroying: bool,
        mount_path: str,
        read_only: bool,
        driver_opts: dict[str, str] | None = None,
    ):
        self.__name = name
        self.__driver = driver
        self.__driver_opts: dict[str, str] = (
            driver_opts.copy() if driver_opts else dict()
        )
        self.__delete_on_destroying = delete_on_destroying
        self.__mount_path = mount_path
        self.__owner_name = owner_name
        self.__read_only = read_only

    def name(self) -> str:
        return self.__name

    def driver(self) -> str:
        return self.__driver

    def delete_status(self) -> bool:
        return self.__delete_on_destroying

    def options(self) -> dict[str, str]:
        return self.__driver_opts.copy()

    def mount_path(self) -> str:
        return self.__mount_path

    def owner_name(self) -> str:
        return self.__owner_name

    def read_only(self) -> bool:
        return self.__read_only
