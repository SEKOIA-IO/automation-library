from stix2patterns.pattern import Pattern
import six
from .models import (
    GetBlockListActionResponse,
    ItemsModel,
    HashModel,
    PathModel,
    ConnectionModel,
    DetailsModel,
)


def handle_uri(uri: str) -> str:
    """
    Handle the URI for the asset connector.

    Args:
        uri (str): The URI to handle.

    Returns:
        str: The handled URI.
    """
    uri = uri.rstrip("/")

    if uri.startswith("http://"):
        uri = uri.replace("http://", "https://", 1)

    if not uri.startswith("https://") and not uri.startswith("mock://"):
        uri = f"https://{uri}"

    return uri


def is_a_supported_stix_indicator(stix_object):
    # Check if object is an indicator
    if stix_object.get("type") != "indicator":
        return False

    # Check if indicator is STIX
    pattern_type = stix_object.get("pattern_type")
    return pattern_type is None or pattern_type == "stix"


def stix_to_indicators(stix_object, supported_types_map):
    """
    Extract indicators type and value from the STIX pattern.

    supported_types_map is used to define the mapping from STIX pattern
    to the different IOCs types.
    "stix_root_key": {"stix_sub_key": "target_type"}
    Example with ipv4:
    Mapping with "ipv4-addr": {"value": "ipv4"} for IOC "[ipv4-addr:value = 'X.X.X.X']"
    """
    if not is_a_supported_stix_indicator(stix_object):
        return []
    parsed_pattern = Pattern(stix_object["pattern"])
    results = []
    for observable_type, comparisons in six.iteritems(parsed_pattern.inspect().comparisons):
        if observable_type not in supported_types_map:
            continue

        for path, operator, value in comparisons:
            if operator != "=":
                continue
            ioc_type = observable_type
            ioc_value = value.strip("'")
            results.append({"type": ioc_type, "value": ioc_value, "path": path})

    return results


def parse_get_block_list_response(response: dict) -> GetBlockListActionResponse:
    items = response["result"].get("items", [])
    itemModels = []
    for item in items:
        type = item.get("type", "")
        response_details = item.get("details", {})
        details: DetailsModel = DetailsModel()
        match type:
            case "hash":
                details = HashModel(**response_details)
            case "path":
                details = PathModel(**response_details)
            case "connection":
                details = ConnectionModel(**response_details)
            case _:
                continue

        itemModel = ItemsModel(type=type, id=item.get("id", ""), details=details)
        itemModels.append(itemModel)

    blockList = GetBlockListActionResponse(
        total=response.get("total", 0),
        page=response.get("page", 1),
        perPage=response.get("perPage", 30),
        pagesCount=response.get("pagesCount", 0),
        items=itemModels,
    )

    return blockList
