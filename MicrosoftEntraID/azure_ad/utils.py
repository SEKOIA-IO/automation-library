import secrets
import string

PASSWORD_DEFAULT_LENGTH: int = 10  # Min length based on microsoft docs is 8
PASSWORD_MIN_LOWER: int = 1
PASSWORD_MIN_UPPER: int = 1
PASSWORD_MIN_DIGITS: int = 1
PASSWORD_MIN_SPECIALS: int = 1
PASSWORD_SPECIALS: str = "!@#$%^&*()-_=+[]{}:,.?"


def generate_password() -> str:
    """
    Generates a password that satisfies common Entra password policies:
    - at least one lower, upper, digit, special
    - reasonable default length (20)

    https://learn.microsoft.com/en-us/entra/identity/authentication/concept-password-ban-bad-combined-policy
    """
    rng = secrets.SystemRandom()

    lower = [rng.choice(string.ascii_lowercase) for _ in range(PASSWORD_MIN_LOWER)]
    upper = [rng.choice(string.ascii_uppercase) for _ in range(PASSWORD_MIN_UPPER)]
    digits = [rng.choice(string.digits) for _ in range(PASSWORD_MIN_DIGITS)]
    special = [rng.choice(PASSWORD_SPECIALS) for _ in range(PASSWORD_MIN_SPECIALS)]

    remaining_len = PASSWORD_DEFAULT_LENGTH - (
        PASSWORD_MIN_LOWER + PASSWORD_MIN_UPPER + PASSWORD_MIN_DIGITS + PASSWORD_MIN_SPECIALS
    )
    alphabet = string.ascii_letters + string.digits + PASSWORD_SPECIALS
    remaining = [rng.choice(alphabet) for _ in range(remaining_len)]

    password_chars = lower + upper + digits + special + remaining
    rng.shuffle(password_chars)

    return "".join(password_chars)
