from datetime import datetime
from typing import Any
from uuid import uuid4

import nanoid
from faker import Faker


class IntakeGenerator:
    faker: Faker

    def create_fake_intake(
        self,
        entity,
        name: str | None = None,
        uuid: str | None = None,
        community_uuid: str | None = None,
        created_at: datetime | None = None,
        created_by: str | None = None,
        created_by_type: str = "avatar",
        format_uuid: str | None = None,
    ) -> dict[str, Any]:
        if uuid is None:
            uuid = str(uuid4())

        if name is None:
            name = self.faker.word()

        if community_uuid is None:
            community_uuid = entity["community_uuid"]

        if created_by is None:
            created_by = str(uuid4())

        if created_at is None:
            created_at = datetime.utcnow()

        new_intake = {
            "intake_key": nanoid.generate(
                alphabet="123456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ", size=32
            ),
            "community_uuid": community_uuid,
            "uuid": uuid,
            "name": name,
            "entity_uuid": entity["uuid"],
            "format_uuid": format_uuid or str(uuid4()),
            "created_at": created_at,
            "created_by": created_by,
            "created_by_type": created_by_type,
        }

        return new_intake
