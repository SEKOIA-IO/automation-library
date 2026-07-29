from datetime import datetime
from uuid import uuid4

import orjson
from ldap3 import ALL_ATTRIBUTES
from pydantic import BaseModel

from .actions_base import MicrosoftADAction


class SearchArguments(BaseModel):
    search_filter: str
    basedn: str
    attributes: list[str] | None = None
    to_file: bool = False


class SearchAction(MicrosoftADAction):
    name = "Search"
    description = "Search in your AD"

    def make_serializable(self, data):
        if isinstance(data, bytes):
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return data.hex()
        elif isinstance(data, (list, tuple)):
            return [self.make_serializable(item) for item in data]
        elif hasattr(data, "entry_to_json"):
            return data.entry_to_json()
        elif isinstance(data, dict):
            return {key: self.make_serializable(value) for key, value in data.items()}
        if isinstance(data, datetime):
            return data.isoformat()
        else:
            return data

    def transform_ldap_results(self, entries):
        transformed = []
        for entry in entries:
            if "attributes" in entry:
                serialized_entry = self.make_serializable(dict(entry["attributes"]))
                transformed.append(serialized_entry)
        return transformed

    def run(self, arguments: SearchArguments) -> dict:
        attributes = arguments.attributes or ALL_ATTRIBUTES
        try:
            self.client.search(
                search_base=arguments.basedn, search_filter=arguments.search_filter, attributes=attributes
            )
        except Exception as e:
            raise Exception(f"Failed to search in this base {arguments.basedn}") from e

        result = self.transform_ldap_results(self.client.response)
        if arguments.to_file:
            filename = f"output-{uuid4()}.json"
            with self._data_path.joinpath(filename).open("w") as f:
                if isinstance(result, str):
                    f.write(result)
                else:
                    try:
                        f.write(orjson.dumps(result, default=str).decode("utf-8"))
                    except (TypeError, ValueError):
                        f.write(str(result))
            return {"output_path": filename}
        else:
            return {"search_result": result}
