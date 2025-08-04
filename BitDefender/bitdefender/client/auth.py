from requests.auth import AuthBase
import base64

class BitdefenderApiAuth(AuthBase):
    """
    Authentication class for Bitdefender API.
    This class is used to authenticate requests to the Bitdefender API.
    """

    def __init__(self, api_key: str):
        """
        Initialize the BitdefenderAuth with an API key.

        :param api_key: The API key for authenticating with the Bitdefender API.
        """
        self.api_key = api_key

    def __call__(self, request):
        """
        Modify the request to include the API key in the headers.

        :param request: The request object to modify.
        :return: The modified request object.
        """
        login_string = f'{self.api_key}:'
        encoded_bytes = base64.b64encode(login_string.encode())
        encoded_user_pass_sequence = str(encoded_bytes, 'utf-8')
        request.headers['Content-Type'] = 'application/json'
        request.headers['Authorization'] = f'Basic {encoded_user_pass_sequence}'
        return request