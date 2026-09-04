
from enum import Enum
from pydantic import BaseModel

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
class Placeholder(BaseModel):
    type: PlaceholderType
    value: str | int

class User(BaseModel):
    name: str
    id: int
    is_bot: bool = False

class Channel(BaseModel):
    id: int
    name: str

class Guild(BaseModel):
    id: int
    name: str

class Command(BaseModel):
    name: str
    description: str
    service:str
    tag:str

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
class CommandRegister(BaseModel):
    command:list[Command]

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