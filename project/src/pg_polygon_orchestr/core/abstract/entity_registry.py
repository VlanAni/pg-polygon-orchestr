from .entity import Entity
from .deployer import Deployer
import uuid

from collections.abc import Mapping


class EntityRegistry:

    def __init__(self) -> None:
        self.__name_map: dict[str, Entity] = dict()
        self.__uuid_map: dict[uuid.UUID, Entity] = dict()

    def put_object_in_registry(self, deployer: Deployer, entity: Entity) -> bool:
        input_entity_name = entity.inf_name()
        input_entity_uuid = entity.get_id()

        if self.__uuid_map.get(input_entity_uuid, None) is not None:
            return False

        if self.__name_map.get(input_entity_name, None) is not None:
            return False

        self.__name_map[input_entity_name] = entity
        self.__uuid_map[input_entity_uuid] = entity

        return True

    def pop_object_from_registry(self, deployer: Deployer, entity: Entity) -> None:
        input_entity_name = entity.inf_name()
        input_entity_uuid = entity.get_id()

        try:
            self.__name_map.pop(input_entity_name)
            self.__uuid_map.pop(input_entity_uuid)
        except Exception:
            pass

    def get_entity_by_id(self, uuid: uuid.UUID) -> Entity | None:
        return self.__uuid_map.get(uuid, None)

    def get_entity_by_name(self, name: str) -> Entity | None:
        return self.__name_map.get(name, None)

    def get_name_map(self) -> Mapping[str, Entity]:
        return self.__name_map

    def get_uuid_map(self) -> Mapping[uuid.UUID, Entity]:
        return self.__uuid_map

    def clear(self) -> None:
        self.__uuid_map.clear()
        self.__name_map.clear()
