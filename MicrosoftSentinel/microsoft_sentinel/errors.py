class IncidentsForwardError(Exception):
    """
    Some incidents of a batch were not accepted by the intake: the batch is collected again on the next poll.
    """
