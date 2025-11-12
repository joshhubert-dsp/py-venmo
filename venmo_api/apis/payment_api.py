import uuid
from typing import Literal

from venmo_api.apis.api_client import ApiClient, ValidatedResponse
from venmo_api.apis.api_util import deserialize
from venmo_api.apis.exception import (
    AlreadyRemindedPaymentError,
    ArgumentMissingError,
    GeneralPaymentError,
    NoPaymentMethodFoundError,
    NoPendingPaymentToUpdateError,
    NotEnoughBalanceError,
)
from venmo_api.models.page import Page
from venmo_api.models.payment import (
    EligibilityToken,
    Payment,
    PaymentAction,
    PaymentMethod,
    PaymentMethodRole,
    TransferDestination,
    TransferPostResponse,
)
from venmo_api.models.user import PaymentPrivacy, User


class PaymentApi:
    def __init__(
        self, profile: User, api_client: ApiClient, balance: float | None = None
    ):
        super().__init__()
        self._profile = profile
        self._balance = balance
        self._api_client = api_client
        self._payment_error_codes = {
            "already_reminded_error": 2907,
            "no_pending_payment_error": 2901,
            "no_pending_payment_error2": 2905,
            "not_enough_balance_error": 13006,
        }

    def get_charge_payments(self, limit=100000) -> Page[Payment]:
        """
        Get a list of charge ongoing payments (pending request money)
        :param limit:
        :return:
        """
        return self._get_payments(action="charge", limit=limit)

    def get_pay_payments(self, limit=100000) -> Page[Payment]:
        """
        Get a list of pay ongoing payments (pending requested money from your profile)
        :param limit:
        :return:
        """
        return self._get_payments(action="pay", limit=limit)

    def remind_payment(self, payment: Payment = None, payment_id: int = None) -> bool:
        """
        Send a reminder for payment/payment_id
        :param payment: either payment object or payment_id must be be provided
        :param payment_id:
        :return: True or raises AlreadyRemindedPaymentError
        """

        # if the reminder has already sent
        payment_id = payment_id or payment.id
        action = "remind"
        response = self._update_payment(action=action, payment_id=payment_id)

        # if the reminder has already sent
        if "error" in response.body:
            if (
                response.body["error"]["code"]
                == self._payment_error_codes["no_pending_payment_error2"]
            ):
                raise NoPendingPaymentToUpdateError(payment_id, action)
            raise AlreadyRemindedPaymentError(payment_id=payment_id)
        return True

    def cancel_payment(self, payment: Payment = None, payment_id: int = None) -> bool:
        """
        Cancel the payment/payment_id provided. Only applicable to payments you have access to (requested payments)
        :param payment:
        :param payment_id:
        :return: True or raises NoPendingPaymentToCancelError
        """
        # if the reminder has already sent
        action = "cancel"
        payment_id = payment_id or payment.id
        response = self._update_payment(action=action, payment_id=payment_id)

        if "error" in response.body:
            raise NoPendingPaymentToUpdateError(payment_id, action)
        return True

    def get_payment_methods(self) -> Page[PaymentMethod]:
        """
        Get a list of available payment_methods
        :return:
        """
        response = self._api_client.call_api(
            resource_path="/payment-methods", method="GET"
        )
        return deserialize(response=response, data_type=PaymentMethod)

    def send_money(
        self,
        amount: float,
        note: str,
        target_user_id: str,
        funding_source_id: str = None,
        privacy_setting: PaymentPrivacy = PaymentPrivacy.PRIVATE,
    ) -> Payment:
        """
        send [amount] money with [note] to the ([target_user_id] or [target_user]) from the [funding_source_id]
        If no [funding_source_id] is provided, it will find the default source_id and uses that.
        :param amount: <float>
        :param note: <str>
        :param funding_source_id: <str> Your payment_method id for this payment
        :param privacy_setting: <PaymentPrivacy> PRIVATE/FRIENDS/PUBLIC (enum)
        :param target_user_id: <str>
        :param target_user: <User>
        :return: <bool> Either the transaction was successful or an exception will rise.
        """

        return self._send_or_request_money(
            amount=amount,
            note=note,
            is_send_money=True,
            funding_source_id=funding_source_id,
            target_user_id=target_user_id,
            privacy_setting=privacy_setting.value,
        )

    def request_money(
        self,
        amount: float,
        note: str,
        target_user_id: str,
        privacy_setting: PaymentPrivacy = PaymentPrivacy.PRIVATE,
    ) -> Payment:
        """
        Request [amount] money with [note] from the ([target_user_id] or [target_user])
        :param amount: <float> amount of money to be requested
        :param note: <str> message/note of the transaction
        :param privacy_setting: <PaymentPrivacy> PRIVATE/FRIENDS/PUBLIC (enum)
        :param target_user_id: <str> the user id of the person you are asking the money from
        :param target_user: <User> The user object or user_id is required
        :return: <bool> Either the transaction was successful or an exception will rise.
        """
        return self._send_or_request_money(
            amount=amount,
            note=note,
            is_send_money=False,
            funding_source_id=None,
            target_user_id=target_user_id,
            privacy_setting=privacy_setting.value,
        )

    def get_transfer_destinations(
        self, trans_type: Literal["standard", "instant"]
    ) -> Page[TransferDestination]:
        """
        Get a list of available transfer destination options for the given type
        :return:
        """
        resource_path = "/transfers/options"
        response = self._api_client.call_api(resource_path=resource_path, method="GET")
        return deserialize(
            response, TransferDestination, [trans_type, "eligible_destinations"]
        )

    def initiate_transfer(
        self,
        destination_id: str,
        amount: float | None = None,
        trans_type: Literal["standard", "instant"] = "standard",
    ) -> TransferPostResponse:
        if amount is None and self._balance is not None:
            amount = self._balance
        else:
            raise ValueError("must pass a transfer amount if no balance available")

        amount_cents = round(amount * 100)
        body = {
            "amount": amount_cents,
            "destination_id": destination_id,
            "transfer_type": trans_type,
            # TODO should this have a fee subtracted? don't feel like testing
            "final_amount": amount_cents,
        }
        response = self._api_client.call_api(
            resource_path="/transfers", body=body, method="POST"
        )
        return deserialize(response, TransferPostResponse)

    def get_default_payment_method(self) -> PaymentMethod:
        """
        Search in all payment_methods and find the one that has payment_role of Default
        :return:
        """
        payment_methods = self.get_payment_methods()

        for p_method in payment_methods:
            if not p_method:
                continue

            if p_method.role == PaymentMethodRole.DEFAULT:
                return p_method

        raise NoPaymentMethodFoundError()

    # --- HELPERS ---

    def _get_eligibility_token(
        self,
        amount: float,
        note: str,
        target_id: str,
        action: str = "pay",
        country_code: str = "1",
        target_type: str = "user_id",
    ) -> EligibilityToken:
        """
        Generate eligibility token which is needed in payment requests
        :param amount: <float> amount of money to be requested
        :param note: <str> message/note of the transaction
        :param target_id: <int> the user id of the person you are sending money to
        :param funding_source_id: <str> Your payment_method id for this payment
        :param action: <str> action that eligibility token is used for
        :param country_code: <str> country code, not sure what this is for
        :param target_type: <str> set by default to user_id, but there are probably other target types
        """
        body = {
            "funding_source_id": "",
            "action": action,
            "country_code": country_code,
            "target_type": target_type,
            "note": note,
            "target_id": target_id,
            "amount": round(amount * 100),
        }
        response = self._api_client.call_api(
            resource_path="/protection/eligibility", body=body, method="POST"
        )
        return deserialize(response=response, data_type=EligibilityToken)

    def _update_payment(
        self, action: Literal["remind", "cancel"], payment_id: str
    ) -> ValidatedResponse:
        if not payment_id:
            raise ArgumentMissingError(arguments=("payment", "payment_id"))

        return self._api_client.call_api(
            resource_path=f"/payments/{payment_id}",
            body={"action": action},
            method="PUT",
            ok_error_codes=list(self._payment_error_codes.values())[:-1],
        )

    def _get_payments(self, action: PaymentAction, limit: int) -> Page[Payment]:
        """
        Get a list of ongoing payments with the given action
        :return:
        """
        parameters = {"action": action, "actor": self._profile.id, "limit": limit}
        # other params `status: pending,held`
        response = self._api_client.call_api(
            resource_path="/payments",
            params=parameters,
            method="GET",
        )
        return deserialize(response=response, data_type=Payment)

    def _send_or_request_money(
        self,
        amount: float,
        note: str,
        is_send_money: bool,
        funding_source_id: str,
        target_user_id: str,
        privacy_setting: PaymentPrivacy = PaymentPrivacy.PRIVATE,
        eligibility_token: str | None = None,
    ) -> Payment | None:
        """
        Generic method for sending and requesting money
        :param amount:
        :param note:
        :param is_send_money:
        :param funding_source_id:
        :param privacy_setting:
        :param target_user_id:
        :param eligibility_token:
        :return:
        """

        amount = abs(amount)
        if not is_send_money:
            amount = -amount

        body = {
            "uuid": str(uuid.uuid4()),
            "user_id": target_user_id,
            "audience": privacy_setting,
            "amount": round(amount, 2),
            "note": note,
        }

        if is_send_money:
            if not funding_source_id:
                funding_source_id = self.get_default_payment_method().id
            if not eligibility_token:
                eligibility_token = self._get_eligibility_token(
                    amount, note, target_user_id
                ).eligibility_token
            body.update({"eligibility_token": eligibility_token})
            body.update({"funding_source_id": funding_source_id})

        response = self._api_client.call_api(
            resource_path="/payments", method="POST", body=body
        )
        # handle 200 status code errors
        error_code = response.body["data"].get("error_code")
        if error_code:
            if error_code == self._payment_error_codes["not_enough_balance_error"]:
                raise NotEnoughBalanceError(amount, target_user_id)

            error = response.body["data"]
            raise GeneralPaymentError(f"{error.get('title')}\n{error.get('error_msg')}")

        # if no exception raises, then it was successful
        return deserialize(response, Payment, nested_response=["payment"])
