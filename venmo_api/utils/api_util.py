from enum import Enum
from typing import Any

from pydantic import BaseModel

from venmo_api import ArgumentMissingError, Page, User


def deserialize(
    response: dict, data_type: type[BaseModel], nested_response: list[str] | None = None
) -> BaseModel | Page[BaseModel]:
    """Extract one or a list of Objects from the api_client structured response.
    :param response: <dict>
    :param data_type: <Generic>
    :param nested_response: <list[str]> Optional. Loop through the body
    :return: a single <Object> or a <Page> of objects (Objects can be User/Transaction/Payment/PaymentMethod)
    """

    body = response.get("body")
    if not body:
        raise Exception("Can't get an empty response body.")

    data = body.get("data")
    nested_response = nested_response or []
    for nested in nested_response:
        temp = data.get(nested)
        if not temp:
            raise ValueError(f"Couldn't find {nested} in the {data}.")
        data = temp

    # Return a list of <class> data_type
    if isinstance(data, list):
        return __get_objs_from_json_list(json_list=data, data_type=data_type)

    return data_type.model_validate(data)


def wrap_callback(
    callback, data_type: type[BaseModel], nested_response: list[str] | None = None
):
    """
    :param callback: <function> Function that was provided by the user
    :param data_type: <class> It can be either User or Transaction
    :param nested_response: <list[str]> Optional. Loop through the body
    :return wrapped_callback: <function> or <NoneType> The user callback wrapped for json parsing.
    """
    if not callback:
        return None

    def wrapper(response):
        if not data_type:
            return callback(True)

        deserialized_data = deserialize(
            response=response, data_type=data_type, nested_response=nested_response
        )
        return callback(deserialized_data)

    return wrapper


def __get_objs_from_json_list(
    json_list: list[Any], data_type: type[BaseModel]
) -> Page[BaseModel]:
    """Process JSON for User/Transaction
    :param json_list: <list> a list of objs
    :param data_type: <class> User/Transaction/Payment/PaymentMethod
    :return: <page>
    """
    result = Page()
    for obj in json_list:
        data_obj = data_type.model_validate(obj)
        result.append(data_obj)

    return result


class Colors(Enum):
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def warn(message):
    """
    print message in Red Color
    :param message:
    :return:
    """
    print(Colors.WARNING.value + message + Colors.ENDC.value)


def confirm(message):
    """
    print message in Blue Color
    :param message:
    :return:
    """
    print(Colors.OKBLUE.value + message + Colors.ENDC.value)


def get_user_id(user, user_id):
    """
    Checks at least one user_id exists and returns it
    :param user_id:
    :param user:
    :return user_id:
    """
    if not user and not user_id:
        raise ArgumentMissingError(arguments=("target_user_id", "target_user"))

    if not user_id:
        if type(user) != User:
            raise ArgumentMissingError(
                f"Expected {User} for target_user, but received {type(user)}"
            )

        user_id = user.id

    return user_id
