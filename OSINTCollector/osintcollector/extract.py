import gzip
import io
import itertools
import json
import sys
import uuid
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta

import magic
import pytz
from osintcollector.errors import GZipError, MagicLibError, UnzipError
from osintcollector.validators import is_valid


def ungzip(data):
    """
    unzip data content
    """
    try:
        return gzip.decompress(data)
    except Exception:
        raise GZipError(sys.exc_info())


def unzip(data):
    """
    unzip data content
    """
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        filename = z.namelist()
        if filename:
            data = z.read(filename[0])
        return data
    except Exception:
        raise UnzipError(sys.exc_info())


def magic_data(data):
    """
    Detect data type and format it to string
    """
    try:
        mime = magic.Magic(mime=True)
        _type = mime.from_buffer(data)
        if _type == "text/plain":
            return data
        elif _type == "application/gzip":
            return ungzip(data)
        elif _type == "application/zip":
            return unzip(data)
    except Exception:
        raise MagicLibError(error=sys.exc_info())
    return data


IDENTITY_NAMESPACE = uuid.UUID("384ca57e-627e-4e43-a297-655eab1004af")


def stix_timestamp(dt):
    d_with_timezone = dt.replace(tzinfo=pytz.UTC)
    return d_with_timezone.isoformat()


def create_identity(configuration):
    """
    Creates a STIX object for the provided identity.

    :param configuration: the configuration of the identity
    :type configuration: dict
    :return: a STIX identity object
    :rtype: stix2.Identity
    :raises ValueError: if the identity has no name
    """

    if configuration.get("name") is None:
        raise ValueError("Cannot create an identity with no name")

    identity_uuid = uuid.uuid5(IDENTITY_NAMESPACE, configuration["name"])

    return {
        "id": f"identity--{identity_uuid}",
        "type": "identity",
        "name": configuration.get("name"),
        "identity_class": "organization",
        "description": configuration.get("description", ""),
        "contact_information": configuration.get("contact", ""),
    }


def _compute_array_item(item: dict, results: list):
    array_keys: list = []
    array_values: list = []

    # See if we have any array keys
    for key in item:
        if key.startswith("*"):
            array_keys.append(key)

    # Make sure the dict does not keep array values
    if array_keys:
        for key in array_keys:
            array_values.append(item.pop(key))

        for combination in itertools.product(*array_values):
            for i, value in enumerate(combination):
                item[array_keys[i][1:]] = value

            results.append(item.copy())
    else:
        results.append(item)


def compute_arrays(data: list) -> list:
    """
    Expand extracted data, duplicating the objects for each value in fields prefixed with '*'
    """
    results: list = []

    for item in data:
        _compute_array_item(item, results)

    return results


def add_context_and_tags(source: dict, observable: dict, context: dict | None = None):
    now = datetime.utcnow()

    if context:
        context.pop("type", None)

        observable["x_inthreat_history"] = [
            {
                "name": source["name"],
                "date": datetime.isoformat(now) + "Z",
                "value": context,
            }
        ]

    if source.get("tags"):
        observable["x_inthreat_tags"] = []

        for tag_name in source["tags"]:
            tag = {"name": tag_name, "valid_from": datetime.isoformat(now) + "Z"}

            if source.get("tags_valid_for"):
                tag["valid_until"] = datetime.isoformat(now + timedelta(days=int(source["tags_valid_for"]))) + "Z"

            observable["x_inthreat_tags"].append(tag)


def parse_value_port(value) -> tuple:
    value, *remaining = value.split(":", 1)
    port = None
    if remaining:
        try:
            port = int(remaining[0])
        except ValueError:
            pass
    return value, port


def _create_observable(observable: dict, source: dict, identity: dict, serialized_observables: set) -> list[dict]:
    new_observables: dict = defaultdict(dict)
    observables = []
    port = None
    for path, value in observable.items():
        parts = path.split(":")
        observable_type = parts[0]
        if len(parts) == 1:
            path = ["value"]
        else:
            path = parts[1].split(".")

        if observable_type == "ipv4-addr":
            value, port = parse_value_port(value)

        if is_valid(observable_type, path, value):
            observable = new_observables[observable_type]
            observable["type"] = observable_type

            for field in path[:-1]:
                observable.setdefault(field, {})
                observable = observable[field]

            observable[path[-1]] = value

    context = new_observables.pop("context", {})
    if port:
        context["port"] = port
    for observable in new_observables.values():
        serialized = json.dumps(observable, sort_keys=True)

        # Skip duplicates
        if serialized in serialized_observables:
            continue

        serialized_observables.add(serialized)

        add_context_and_tags(source, observable, context)

        observable["x_inthreat_sources_refs"] = [identity["id"]]
        observables.append(observable)
    return observables


def create_observables(source: dict, identity: dict, data: list):
    observables: list = []
    serialized_observables: set = set()

    for observable in compute_arrays(data):
        observables += _create_observable(observable, source, identity, serialized_observables)

    return observables
