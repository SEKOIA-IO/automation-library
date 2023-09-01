# third parties
from typing import Any
from uuid import uuid4

import orjson
from _io import StringIO
from lxml import etree
from lxml.html import document_fromstring

# internal
from sekoia_automation.action import Action
from sekoia_automation.exceptions import MissingActionArgumentError, MissingActionArgumentFileError  # noqa


class FileUtilsReadXMLFile(Action):
    """
    Action to read the content of a file and parse its HTML.

    It use XML parser (lxml) to search for a specifics element
    in the HTML or XML using XPath.
    """

    def run(self, arguments) -> dict:
        result = None
        content = self._read_file("file", arguments)
        source_type = arguments.get("source_type", "html").lower()

        if source_type == "xml":
            # Strict XML parsing
            f = StringIO(content)
            tree = etree.parse(f)
        else:
            # Treat as the default input type: HTML
            tree = document_fromstring(content)

        if arguments.get("xpath") is not None:
            matched_value = tree.xpath(arguments.get("xpath"))
            return_list = arguments.get("return_list", False)
            if len(matched_value) == 1 and not return_list:
                result = matched_value[0]
            elif len(matched_value) > 1 or return_list:
                result = matched_value
        else:
            result = content

        return self._save_file(result, arguments)

    def _read_file(self, name: str, arguments: dict, required: bool = True) -> str:  # type: ignore[return]
        """Read file content"""

        if name in arguments:
            self._result_as_file = False
            return arguments[name]
        elif f"{name}_path" in arguments:
            filepath = self._data_path.joinpath(arguments[f"{name}_path"])
            if not filepath.is_file():
                raise MissingActionArgumentFileError(filepath)

            with filepath.open("r") as f:
                return f.read()
        else:
            if required:
                raise MissingActionArgumentError(name)

    def _save_file(self, result: Any, arguments: dict) -> dict:
        if not arguments.get("to_file", False):
            return {"output": result}

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
