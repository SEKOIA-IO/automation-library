import time


def time_to_sleep(duration: float) -> float:
    """
    Calculate the time to sleep based on the given duration.

    The purpose is to split long sleep durations into smaller chunks
    to improve accuracy.
    """
    # For 1 hour to 5 minutes, sleep for a third of the duration
    if duration > 300:
        return duration / 3
    # For 5 minutes to 20 seconds, sleep for a quarter of the duration
    elif duration > 20:
        return duration / 4
    # For 20 seconds to 1 second, sleep for a tenth of the duration, capped at 1 second
    elif duration > 1:
        return max(duration / 10, 1)
    # For durations less than or equal to 1 second, sleep for the full duration
    else:
        return duration


def accurate_sleep(seconds: int) -> None:
    """
    A more accurate sleep function for long breaks.

    :param seconds: Number of seconds to sleep.

    According to Python documentation, time.sleep() may sleep for longer
    than the specified time due to OS scheduling
    (See https://docs.python.org/3/library/time.html#time.sleep).

    This function ensures that we sleep for at least the specified time.
    """
    # Calculate the target end time
    target_time = time.time() + float(seconds)

    # Loop until the current time reaches the target time
    while time.time() < target_time:

        # Calculate remaining time to sleep
        remaining_sleep = target_time - time.time()

        # Sleep for a calculated time chunk
        if remaining_sleep > 0.3:
            time.sleep(time_to_sleep(remaining_sleep))
        else:
            time.sleep(0)
