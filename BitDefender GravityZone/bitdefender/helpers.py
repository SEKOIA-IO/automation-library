from .models import (
    ItemsModel,
    HashModel,
    PathModel,
    ConnectionModel,
    DetailsModel,
    RuleModel,
    BlockListModel,
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


def parse_push_block(arguments: dict) -> BlockListModel:
    type = arguments.get("type", "")
    rules = arguments.get("rules", [])
    if not type or not rules:
        raise ValueError("Invalid arguments: 'type' and 'rules' are required")

    ruleModels = []
    for rule in rules:
        details: DetailsModel = DetailsModel()
        if "details" not in rule:
            raise ValueError("Invalid rule: 'details' is required")
        match type:
            case "hash":
                details = HashModel(**rule["details"])
            case "path":
                details = PathModel(**rule["details"])
            case "connection":
                details = ConnectionModel(**rule["details"])
            case _:
                raise ValueError(f"Unsupported type: {type}")

        ruleModels.append(RuleModel(details=details))

    return BlockListModel(type=type, rules=ruleModels)
