import random
from typing import Any
from uuid import UUID, uuid4

from faker import Faker


class EntityGenerator:
    faker: Faker

    def create_fake_entity(
        self,
        name: str | None = None,
        entity_id: int | None = None,
        community_uuid: str | None = None,
        description: str | None = None,
        alerts_generation: UUID | None = None,
    ) -> dict[str, Any]:
        if name is None:
            name = self.faker.word()

        if community_uuid is None:
            community_uuid = str(uuid4())

        if entity_id is None:
            entity_id = random.randint(0, 1000)

        new_entity = {
            "name": name,
            "community_uuid": community_uuid,
            "entity_id": entity_id,
            "alerts_generation": alerts_generation,
            "description": description,
        }

        return new_entity
