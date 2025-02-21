from .base import MicrosoftADAction
from pydantic.v1 import BaseModel
from typing import List
from ldap3 import ALL_ATTRIBUTES
from ldap3.core.timezone import OffsetTzInfo
from datetime import datetime
from uuid import uuid4
import orjson
from pathlib import Path


class SearchArguments(BaseModel):
    search_filter: str
    basedn: str
    attributes: List[str] | None
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
        except:
            raise Exception(f"Failed to search in this base {arguments.basedn}")

        result = self.transform_ldap_results(self.client.response)
        if arguments.to_file:
            filename = f"output-{uuid4()}.json"
            with self._data_path.joinpath(filename).open("w") as f:
                if isinstance(result, str):
                    f.write(result)
                else:
                    try:
                        f.write(orjson.dumps(result).decode("utf-8"))
                    except (TypeError, ValueError):
                        f.write(result)
            return {"output_path": filename}
        else:
            return {"search_result": result}
