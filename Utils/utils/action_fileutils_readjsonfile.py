# third parties
from typing import Any
from uuid import uuid4

import orjson
from jsonpath_ng.ext import parse

# internals
from sekoia_automation.action import Action


class FileUtilsReadJSONFile(Action):
    """
    Action to read the content of a file and evaluate its json.

    If no jsonpath is specified, the file content is returned.
    If a jsonpath is specified it returns either the single object that matched with
    the jsonpath or a list with all the matches.
    """

    def run(self, arguments):
        result = None
        content = self.json_argument("file", arguments)

        if arguments.get("jsonpath") is not None:
            matched_values = [match.value for match in parse(arguments["jsonpath"]).find(content)]

            return_list = arguments.get("return_list", False)
            if len(matched_values) == 1 and not return_list:
                result = matched_values[0]
            elif len(matched_values) > 1 or return_list:
                result = matched_values
        else:
            result = content

        return self._send_result(result, arguments)

    def _send_result(self, result: Any, arguments: dict):
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
