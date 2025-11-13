import uuid

from venmo_api.apis.api_client import ApiClient
from venmo_api.apis.api_util import ValidatedResponse, confirm, warn
from venmo_api.apis.exception import AuthenticationFailedError


def random_device_id() -> str:
    """
    Generate a random device id that can be used for logging in.
    NOTE: As of late 2025, they seem to have tightened security around device-ids, so
    that randomly generated ones aren't accepted.
    """
    return str(uuid.uuid4()).upper()


class AuthenticationApi:
    TWO_FACTOR_ERROR_CODE = 81109

    def __init__(
        self, api_client: ApiClient | None = None, device_id: str | None = None
    ):
        super().__init__()

        self._device_id = device_id or random_device_id()
        if not api_client:
            self._api_client = ApiClient(device_id=self._device_id)
        else:
            self._api_client = api_client
            self._api_client.update_device_id(self._device_id)

    def login_with_credentials_cli(self, username: str, password: str) -> str:
        """
        Pass your username and password to get an access_token for using the API.
        :param username: <str> Phone, email or username
        :param password: <str> Your account password to login
        :return: <str>
        """

        # Give warnings to the user about device-id and token expiration
        warn(
            "IMPORTANT: Take a note of your device-id to avoid 2-factor-authentication for your next login."
        )
        print(f"device-id: {self._device_id}")
        warn(
            "IMPORTANT: Your Access Token will NEVER expire, unless you logout manually (client.log_out(token)).\n"
            "Take a note of your token, so you don't have to login every time.\n"
        )

        response = self.authenticate_using_username_password(username, password)

        # if two-factor error
        if response.body.get("error"):
            access_token = self._two_factor_process_cli(response=response)
            self.trust_this_device()
        else:
            access_token = response.body["access_token"]

        confirm("Successfully logged in. Note your token and device-id")
        print(f"access_token: {access_token}\ndevice-id: {self._device_id}")

        return access_token

    @staticmethod
    def log_out(access_token: str) -> bool:
        """
        Revoke your access_token
        :param access_token: <str>
        :return:
        """

        resource_path = "/oauth/access_token"
        api_client = ApiClient(access_token=access_token)

        api_client.call_api(resource_path=resource_path, method="DELETE")

        confirm("Successfully logged out.")
        return True

    def _two_factor_process_cli(self, response: ValidatedResponse) -> str:
        """
        Get response from authenticate_with_username_password for a CLI two-factor process
        :param response:
        :return: <str> access_token
        """

        otp_secret = response.headers.get("venmo-otp-secret")
        if not otp_secret:
            raise AuthenticationFailedError(
                "Failed to get the otp-secret for the 2-factor authentication process. "
                "(check your password)"
            )

        self.send_text_otp(otp_secret=otp_secret)
        user_otp = self._ask_user_for_otp_password()

        access_token = self.authenticate_using_otp(user_otp, otp_secret)
        self._api_client.update_access_token(access_token=access_token)

        return access_token

    def authenticate_using_username_password(
        self, username: str, password: str
    ) -> ValidatedResponse:
        """
        Authenticate with username and password. Raises exception if either be incorrect.
        Check returned response:
            if have an error (response.body.error), 2-factor is needed
            if no error, (response.body.access_token) gives you the access_token
        :param username: <str>
        :param password: <str>
        :return: <dict>
        """
        body = {
            "phone_email_or_username": username,
            "client_id": "1",
            "password": password,
        }

        return self._api_client.call_api(
            resource_path="/oauth/access_token",
            body=body,
            method="POST",
            ok_error_codes=[self.TWO_FACTOR_ERROR_CODE],
        )

    def send_text_otp(self, otp_secret: str) -> ValidatedResponse:
        """
        Send one-time-password to user phone-number
        :param otp_secret: <str> the otp-secret from response_headers.venmo-otp-secret
        :return: <dict>
        """
        response = self._api_client.call_api(
            resource_path="/account/two-factor/token",
            header_params={"venmo-otp-secret": otp_secret},
            body={"via": "sms"},
            method="POST",
        )

        if response.status_code != 200:
            reason = None
            try:
                reason = response.body["error"]["message"]
            finally:
                raise AuthenticationFailedError(
                    f"Failed to send the One-Time-Password to"
                    f" your phone number because: {reason}"
                )

        return response

    def authenticate_using_otp(self, user_otp: str, otp_secret: str) -> str:
        """
        Login using one-time-password, for 2-factor process
        :param user_otp: <str> otp user received on their phone
        :param otp_secret: <str> otp_secret obtained from 2-factor process
        :return: <str> access_token
        """

        header_params = {"venmo-otp": user_otp, "venmo-otp-secret": otp_secret}
        response = self._api_client.call_api(
            resource_path="/oauth/access_token",
            header_params=header_params,
            params={"client_id": 1},
            method="POST",
        )
        return response.body["access_token"]

    def trust_this_device(self, device_id=None):
        """
        Add device_id or self.device_id (if no device_id passed) to the trusted devices on Venmo
        :return:
        """
        device_id = device_id or self._device_id
        header_params = {"device-id": device_id}

        self._api_client.call_api(
            resource_path="/users/devices", header_params=header_params, method="POST"
        )

        confirm("Successfully added your device id to the list of the trusted devices.")
        print(
            f"Use the same device-id: {self._device_id} next time to avoid 2-factor-auth process."
        )

    def get_device_id(self):
        return self._device_id

    def set_access_token(self, access_token):
        self._api_client.update_access_token(access_token=access_token)

    @staticmethod
    def _ask_user_for_otp_password():
        otp = ""
        while len(otp) < 6 or not otp.isdigit():
            otp = input(
                "Enter OTP that you received on your phone from Venmo: (It must be 6 digits)\n"
            )

        return otp
