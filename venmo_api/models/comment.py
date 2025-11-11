from datetime import datetime

from pydantic import BaseModel

from venmo_api import Mention, User


class Comment(BaseModel):
    id: str
    message: str
    date_created: datetime
    mentions: list[Mention]
    user: User
