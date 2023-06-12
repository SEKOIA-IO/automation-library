from typing import Any


def sanitize_node(node: Any) -> Any:
    """
    Sanitize a json node
    """
    if isinstance(node, dict):
        return {key: sanitize_node(value) for key, value in node.items()}
    elif isinstance(node, list):
        return [sanitize_node(child) for child in node]
    elif isinstance(node, int):
        return sanitize_big_int(node)
    else:
        return node


BIG_INT_THRESHOLD = pow(2, 64)


def sanitize_big_int(node: int) -> str | int:
    """
    Convert big int into string
    """
    if node > BIG_INT_THRESHOLD:
        return str(node)
    else:
        return node
