
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


class EmbedFooter(BaseModel):
    text: str  # Текст в самом низу (ОБЯЗАТЕЛЬНО для Footer)
    icon_url: Optional[str] = None  # Маленькая иконка слева от текста
    proxy_icon_url: Optional[str] = None  # Кэшированная иконка (обычно заполняет сам Discord)


class EmbedImage(BaseModel):
    url: str  # URL изображения
    proxy_url: Optional[str] = None  # Кэшированный URL
    height: Optional[int] = None  # Высота картинки в px
    width: Optional[int] = None  # Ширина картинки в px


class EmbedThumbnail(BaseModel):
    url: str  # URL превью (маленькая картинка справа вверху)
    proxy_url: Optional[str] = None
    height: Optional[int] = None
    width: Optional[int] = None


class EmbedVideo(BaseModel):  # Только для чтения (заполняется Discord для плееров)
    url: Optional[str] = None
    proxy_url: Optional[str] = None
    height: Optional[int] = None
    width: Optional[int] = None


class EmbedProvider(BaseModel):  # Только для чтения (например, YouTube / Spotify)
    name: Optional[str] = None
    url: Optional[str] = None


class EmbedAuthor(BaseModel):
    name: str  # Имя автора вверху (ОБЯЗАТЕЛЬНО для Author)
    url: Optional[str] = None  # Ссылка при клике на имя
    icon_url: Optional[str] = None  # Иконка слева от имени
    proxy_icon_url: Optional[str] = None


class EmbedField(BaseModel):
    name: str  # Заголовок поля (до 256 символов)
    value: str  # Содержимое поля (до 1024 символов)
    inline: bool = True  # Располагать в одну строку с соседними (True/False)


class Embed(BaseModel):
    title: Optional[str] = None  # Заголовок карточки (до 256 символов)
    description: Optional[str] = None  # Главный текст карточки (до 4096 символов)
    url: Optional[str] = None  # Ссылка при клике на заголовок (Title)
    timestamp: Optional[datetime] = None  # Время в формате ISO8601/datetime (отображается в подвале)
    color: Optional[int] = None  # Цвет боковой полосы (HEX в integer, напр. 0xFF0000 или 16711680)

    footer: Optional[EmbedFooter] = None  # Подвал карточки
    image: Optional[EmbedImage] = None  # Большая картинка внизу
    thumbnail: Optional[EmbedThumbnail] = None  # Миниатюра справа вверху
    video: Optional[EmbedVideo] = None  # Видео (только для чтения)
    provider: Optional[EmbedProvider] = None  # Провайдер (только для чтения)
    author: Optional[EmbedAuthor] = None  # Блок автора в самом верху
    fields: List[EmbedField] = Field(default_factory=list)  # До 25 колонок/полей


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
    group:str=""
    tag:str
    permission:str = ""
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
    ephemeral: bool =True
    embeds: list[Embed] = Field(default_factory=list)
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

class VoicePlayingCallback(BaseModel):
    success: bool = True
    message: str = ""