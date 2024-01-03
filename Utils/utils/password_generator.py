import secrets
import string
import random
from sekoia_automation.action import Action


class PasswordGenerator(Action):
    def run(self, arguments: dict):
        password_length = arguments.get("password_length", 20)
        number_of_digits = arguments.get("number_of_digits", 1)
        number_of_special_characters = arguments.get("number_of_special_characters", 1)

        if number_of_digits + number_of_special_characters > password_length:
            self.error("number_of_digits + number_of_special_characters must be lower than password_length")
            return

        letters = string.ascii_letters
        digits = string.digits
        special_chars = string.punctuation

        alphabet = letters + digits + special_chars

        chars = [secrets.choice(special_chars) for _ in range(number_of_special_characters)]  # n special chars
        chars += [secrets.choice(digits) for _ in range(number_of_digits)]  # n digits
        chars += [
            secrets.choice(alphabet) for _ in range(password_length - number_of_special_characters - number_of_digits)
        ]  # fill remaining with random
        random.shuffle(chars)  # Shuffle it so char and digits are not always at the beginning
        password = "".join(chars)

        return {"password": password}
