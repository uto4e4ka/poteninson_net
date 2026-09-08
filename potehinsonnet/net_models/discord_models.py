
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field

'''
ENUMS
'''
class PlaceholderType(str, Enum):
    TEXT = "text"
    MENTION = "mention"
    CHANNEL = "channel"
    ROLE = "role"
    USER = "user"

class InteractionType(str, Enum):
    CONNECT = "connect"
    RECONNECT = "reconnect"
    DISCONNECT = "disconnect"

class VoiceChannelUserConnectionType(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    MOVE = "move"

'''
BASE MODELS
'''
class Role(BaseModel):
    id: int
    name: str

class Placeholder(BaseModel):
    type: PlaceholderType
    value: str | int


from datetime import datetime
from pydantic import BaseModel, Field


class User(BaseModel):
    id: int
    name: str
    display_name: str | None = None
    avatar_url: str | None = None
    is_bot: bool = False

    # Роли и голосовой канал
    roles: list[Role] = Field(default_factory=list)
    voice_channel: Channel | None = None

    # Состояние в голосовом канале
    is_deaf: bool = False
    is_mute: bool = False
    is_streaming: bool = False
    is_video: bool = False

    # Метаданные
    joined_at: datetime | None = None

class Channel(BaseModel):
    id: int
    name: str

class Guild(BaseModel):
    id: int
    name: str

class EmbedField(BaseModel):
    name: str
    value: str
    inline: bool = True  # По умолчанию поля располагаются в одну строку


class Embed(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    color: Optional[int] = None  # Например, 0x00FF00 или 65280
    fields: List[EmbedField] = Field(default_factory=list)


'''
Messages
'''

class DiscordMessage(BaseModel):
    user:User
    text:str
    channel_id: int

class NatsMessage(BaseModel):
    service:str
    text: str
    placeholders: dict[str, Placeholder] = {}
    channel_id: int

'''
Command
'''
class CommandArgument(BaseModel):
    name: str
    type: str = "str"
    required: bool = True
    description: str = ""
    default: Any = None

class Command(BaseModel):
    name: str
    description: str
    service:str
    tag:str
    args: list[CommandArgument] = Field(default_factory=list)

class ExecutedArgs(BaseModel):
    name:str
    value: str
    type: str
    is_required: bool = False

class ExecutedCommand(BaseModel):
    service: str
    tag: str
    user: User
    guild: Guild
    channel: Channel
    args: list[ExecutedArgs] = Field(default_factory=list)

class ExecutedCommandResponse(BaseModel):
    message: str
    ephemeral: bool
    embeds: list[Embed]
'''
Voice
'''
class VoiceChannelConnectInteraction(BaseModel):
    channel_id: int
    interaction_type: InteractionType = InteractionType.CONNECT

class VoiceChannelUserConnectionEvent(BaseModel):
    user:User
    after_channel: Channel|None
    before_channel: Channel|None
    guild: Guild|None
    action: VoiceChannelUserConnectionType



class VoiceChannel(BaseModel):
    channel: Channel | None
    guild: Guild | None = None

class VoiceChannelPlaySound(VoiceChannel):
    sound: str
    track_id:str
    before_options: str | None = None
    options: str | None = None

class VoiceConnectionStatus(VoiceChannel):
    connected: bool
    playing: bool = False
    paused: bool = False

class VoiceConnectionRequest(VoiceChannel):
    interaction_type: InteractionType = InteractionType.CONNECT

class VoiceConnectionResponse(VoiceConnectionStatus):
    success: bool = True
    error: str | None = None