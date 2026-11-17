def is_parquet_content(content: bytes) -> bool:
    """
    Check if the current object appears to be an Apache Parquet file.

    Args:
        content: bytes

    Returns:
        bool:
    """
    # Parquet files start and end with the magic bytes PAR1.
    return len(content) >= 8 and content[0:4] == b"PAR1" and content[-4:] == b"PAR1"
