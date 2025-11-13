import os
from json import JSONDecodeError
from random import getrandbits

import orjson
import requests

from venmo_api import PROJECT_ROOT
from venmo_api.apis.api_util import ValidatedResponse
from venmo_api.apis.exception import (
    HttpCodeError,
    InvalidHttpMethodError,
    ResourceNotFoundError,
)
from venmo_api.apis.logging_session import LoggingSession


class ApiClient:
    """
    Generic API Client for the Venmo API
    """

    def __init__(self, access_token: str | None = None, device_id: str | None = None):
        """
        :param access_token: <str> access token you received for your account, not
            including the 'Bearer ' prefix, that's added to the request header.
        """

        super().__init__()

        self.default_headers = orjson.loads(
            (PROJECT_ROOT / "default_headers.json").read_bytes()
        )
        if os.getenv("LOGGING_SESSION"):
            self.session = LoggingSession()
        else:
            self.session = requests.Session()
        self.session.headers.update(self.default_headers)

        self.access_token = access_token
        if access_token:
            self.update_access_token(access_token)
        self.device_id = device_id
        if device_id:
            self.update_device_id(device_id)

        self.update_session_id()
        self.configuration = {"host": "https://api.venmo.com/v1"}

    def update_session_id(self):
        self._session_id = str(getrandbits(64))
        self.default_headers.update({"X-Session-ID": self._session_id})
        self.session.headers.update({"X-Session-ID": self._session_id})

    def update_access_token(self, access_token: str):
        self.access_token = access_token
        self.default_headers.update({"Authorization": "Bearer " + self.access_token})
        self.session.headers.update({"Authorization": "Bearer " + self.access_token})

    def update_device_id(self, device_id: str):
        self.device_id = device_id
        self.default_headers.update({"device-id": self.device_id})
        self.session.headers.update({"device-id": self.device_id})

    def call_api(
        self,
        resource_path: str,
        method: str,
        header_params: dict = None,
        params: dict = None,
        body: dict = None,
        ok_error_codes: list[int] = None,
    ) -> ValidatedResponse:
        """
        Calls API on the provided path

        :param resource_path: <str> Specific Venmo API path
        :param method: <str> HTTP request method
        :param header_params: <dict> request headers
        :param body: <dict> request body will be send as JSON
        :param ok_error_codes: <list[int]> A list of integer error codes that you don't want an exception for.

        :return: response: <dict> {'status_code': <int>, 'headers': <dict>, 'body': <dict>}
        """

        # Update the header with the required values
        header_params = header_params or {}

        if body:  # POST or PUT
            header_params.update({"Content-Type": "application/json; charset=utf-8"})

        url = self.configuration["host"] + resource_path

        # perform request and return response
        processed_response = self.request(
            method,
            url,
            header_params=header_params,
            params=params,
            body=body,
            ok_error_codes=ok_error_codes,
        )
        return processed_response

    def request(
        self,
        method,
        url,
        header_params=None,
        params=None,
        body=None,
        ok_error_codes: list[int] = None,
    ) -> ValidatedResponse:
        """
        Make a request with the provided information using a requests.session
        :param method:
        :param url:
        :param session:
        :param header_params:
        :param params:
        :param body:
        :param ok_error_codes: <list[int]> A list of integer error codes that you don't want an exception for.

        :return:
        """

        if method not in ["POST", "PUT", "GET", "DELETE"]:
            raise InvalidHttpMethodError()

        response = self.session.request(
            method=method, url=url, headers=header_params, params=params, json=body
        )
        validated_response = self._validate_response(
            response, ok_error_codes=ok_error_codes
        )

        return validated_response

    @staticmethod
    def _validate_response(
        response: requests.Response, ok_error_codes: list[int] = None
    ) -> ValidatedResponse:
        """
        Validate and build a new validated response.
        :param response:
        :param ok_error_codes: <list[int]> A list of integer error codes that you don't want an exception for.
        :return:
        """
        headers = response.headers
        try:
            body = response.json()
        except JSONDecodeError:
            body = {}

        built_response = ValidatedResponse(response.status_code, headers, body)

        if response.status_code in range(200, 205) or (
            body and ok_error_codes and body.get("error").get("code") in ok_error_codes
        ):
            return built_response

        elif response.status_code == 400 and body.get("error").get("code") == 283:
            raise ResourceNotFoundError()

        else:
            raise HttpCodeError(response=response)
