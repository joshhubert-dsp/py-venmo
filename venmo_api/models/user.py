from datetime import datetime

from pydantic import BaseModel, EmailStr

from venmo_api.pydantic_models.payment_method import PaymentPrivacy


class User(BaseModel):
    about: str
    date_joined: datetime
    friends_count: int
    is_active: bool
    is_blocked: bool
    friend_status: str | None  # TODO enum?
    profile_picture_url: str
    username: str
    trust_request: str | None  # TODO
    display_name: str
    email: EmailStr | None = None
    first_name: str
    id: str
    identity_type: str  # TODO enum?
    is_group: bool
    last_name: str
    phone: str | None = None
    is_payable: bool
    audience: PaymentPrivacy
