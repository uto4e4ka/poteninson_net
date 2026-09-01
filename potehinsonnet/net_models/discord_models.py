
from enum import Enum
from pydantic import BaseModel


class PlaceholderType(str, Enum):
    TEXT = "text"
    MENTION = "mention"
    CHANNEL = "channel"
    ROLE = "role"
    USER = "user"


class Placeholder(BaseModel):
    type: PlaceholderType
    value: str | int


class NatsMessage(BaseModel):
    service:str
    text: str
    placeholders: dict[str, Placeholder] = {}

class DiscordMessage(BaseModel):
    username:str
    user_id:str
    text:str