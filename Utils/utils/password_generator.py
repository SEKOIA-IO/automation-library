import secrets
import string
from sekoia_automation.action import Action


class PasswordGenerator(Action):
    def run(self, arguments: dict):
        password_length = self.json_argument("password_length", arguments)
        number_of_digits = self.json_argument("number_of_digits", arguments)
        number_of_special_characters = self.json_argument("number_of_special_characters", arguments)

        letters = string.ascii_letters
        digits = string.digits
        special_chars = string.punctuation

        alphabet = letters + digits + special_chars

        while True:
            password = ""
            for i in range(password_length):
                password += "".join(secrets.choice(alphabet))

            if (
                sum(char in special_chars for char in password) >= number_of_special_characters
                and sum(char in digits for char in password) >= number_of_digits
            ):
                break

        return {"password": password}
