from typing import Self

from venmo_api import ApiClient, AuthenticationApi, PaymentApi, UserApi


class Client(object):
    @staticmethod
    def login(username: str, password: str, device_id: str | None = None) -> Self:
        """
        Log in using your credentials and get an access_token to use in the API
        :param username: <str> Can be username, phone number (without +1) or email address.
        :param password: <str> Account's password
        :param device_id: <str> [optional] A valid device-id.

        :return: <str> access_token
        """
        api_client = ApiClient(device_id=device_id)
        access_token = AuthenticationApi(
            api_client, device_id
        ).login_with_credentials_cli(username=username, password=password)
        api_client.update_access_token(access_token)
        return Client(api_client=api_client)

    @staticmethod
    def logout(access_token) -> bool:
        """
        Revoke your access_token. Log out, in other words.
        :param access_token:
        :return: <bool>
        """
        return AuthenticationApi.log_out(access_token=access_token)

    def __init__(
        self,
        access_token: str | None = None,
        device_id: str | None = None,
        api_client: ApiClient | None = None,
    ):
        """
        VenmoAPI Client
        :param access_token: <str> Need access_token to work with the API.
        """
        super().__init__()
        if api_client is None:
            self.__api_client = ApiClient(
                access_token=access_token, device_id=device_id
            )
        else:
            # NOTE: for anything sensitive, makes sense to pass ApiClient instance that
            # you logged in with, since it stores the original csrf_token set at login.
            # Haven't verified that this is absolutely necessary, but seems sensible to
            # align with the app's behavior.
            self.__api_client = api_client
            if access_token is not None:
                # don't allow the possibility of clearing an already set token
                self.__api_client.update_access_token(access_token)

        self.user = UserApi(self.__api_client)
        self.__profile = self.user.get_my_profile()
        self.payment = PaymentApi(profile=self.__profile, api_client=self.__api_client)

    def my_profile(self, force_update=False):
        """
        Get your profile info. It can be cached from the prev time.
        :return:
        """
        if force_update:
            self.__profile = self.user.get_my_profile(force_update=force_update)

        return self.__profile

    @property
    def access_token(self) -> str | None:
        return self.__api_client.access_token

    def log_out_instance(self, token: str | None = None) -> bool:
        """
        Revoke your access_token. Log out, in other words.
        :param access_token:
        :return: <bool>
        """
        if token is None:
            token = self.access_token
        return AuthenticationApi.log_out(token)
