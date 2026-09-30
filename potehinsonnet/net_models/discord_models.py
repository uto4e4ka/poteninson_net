from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# ENUMS
# ============================================================

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


class SoundAction(str, Enum):
    PLAY = "PLAY"
    STOP = "STOP"
    PAUSE = "PAUSE"
    RESUME = "RESUME"


class ComponentButtonStyle(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    SUCCESS = "success"
    DANGER = "danger"
    LINK = "link"


# ============================================================
# BASE MODELS
# ============================================================

class Role(BaseModel):
    id: int
    name: str


class Channel(BaseModel):
    id: int
    name: str


class Guild(BaseModel):
    id: int
    name: str


class Placeholder(BaseModel):
    type: PlaceholderType
    value: str | int


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


# ============================================================
# EMBEDS
# ============================================================

class EmbedFooter(BaseModel):
    text: str
    icon_url: str | None = None
    proxy_icon_url: str | None = None


class EmbedImage(BaseModel):
    url: str
    proxy_url: str | None = None
    height: int | None = None
    width: int | None = None


class EmbedThumbnail(BaseModel):
    url: str
    proxy_url: str | None = None
    height: int | None = None
    width: int | None = None


class EmbedVideo(BaseModel):
    # Только для чтения.
    # Заполняется Discord для видео.
    url: str | None = None
    proxy_url: str | None = None
    height: int | None = None
    width: int | None = None


class EmbedProvider(BaseModel):
    # Только для чтения.
    name: str | None = None
    url: str | None = None


class EmbedAuthor(BaseModel):
    name: str
    url: str | None = None
    icon_url: str | None = None
    proxy_icon_url: str | None = None


class EmbedField(BaseModel):
    name: str
    value: str
    inline: bool = True


class Embed(BaseModel):
    title: str | None = None
    description: str | None = None
    url: str | None = None
    timestamp: datetime | None = None
    color: int | None = None

    footer: EmbedFooter | None = None
    image: EmbedImage | None = None
    thumbnail: EmbedThumbnail | None = None
    video: EmbedVideo | None = None
    provider: EmbedProvider | None = None
    author: EmbedAuthor | None = None

    fields: list[EmbedField] = Field(default_factory=list)


# ============================================================
# DISCORD COMPONENTS
# ============================================================

class ComponentButton(BaseModel):
    """
    Кнопка Discord.

    Для link-кнопки:
        style="link"
        url="https://..."

    Для обычной кнопки:
        custom_id="music:skip"
        style="secondary"
    """

    label: str | None = None
    custom_id: str | None = None

    style: ComponentButtonStyle = ComponentButtonStyle.PRIMARY

    url: str | None = None

    # Например: "▶️", "⏸️", "⏭️"
    emoji: str | None = None

    disabled: bool = False


class TextDisplay(BaseModel):
    """
    Components V2 Text Display.

    Используется для обычного Markdown-текста внутри Container.
    """

    content: str


class Separator(BaseModel):
    """
    Components V2 Separator.
    """

    divider: bool = True

    # 1 = small
    # 2 = large
    spacing: int = 1


class Section(BaseModel):
    content: Optional[str] = None
    components: Optional[List[TextDisplay]] = None
    accessory: ComponentButton | ComponentThumbnail | None = None

class ComponentThumbnail(BaseModel):
    url: str
    description: str | None = None

class MediaItem(BaseModel):
    """
    Один элемент Media Gallery.
    """

    url: str
    description: str | None = None


class MediaGallery(BaseModel):
    """
    Components V2 Media Gallery.
    """

    items: list[MediaItem] = Field(default_factory=list)


class ActionRow(BaseModel):
    """
    Action Row со стандартными Discord-кнопками.
    """

    components: list[ComponentButton] = Field(default_factory=list)


class Container(BaseModel):
    """
    Discord Components V2 Container.

    Внутри Container можно размещать:
    - TextDisplay
    - Section
    - MediaGallery
    - Separator
    - ActionRow
    """

    accent_color: int | None = None
    spoiler: bool = False

    components: list[
        TextDisplay
        | Section
        | MediaGallery
        | Separator
        | ActionRow
    ] = Field(default_factory=list)

class ExecutedComponent(BaseModel):
    id:str
    user:User
    guild:Guild
    channel:Channel
    task_id:str

class ExecutedComponentResponse(BaseModel):
    message:str = ""
    embeds: list[Embed] = Field(
        default_factory=list
    )
    containers: list[Container] = Field(
        default_factory=list
    )
    ephemeral = False


# ============================================================
# MESSAGES
# ============================================================

class DiscordMessage(BaseModel):
    user: User
    text: str
    channel_id: int


class NatsMessage(BaseModel):
    service: str
    text: str

    placeholders: dict[str, Placeholder] = Field(
        default_factory=dict
    )

    channel_id: int

    embeds: list[Embed] = Field(
        default_factory=list
    )

    containers: list[Container] = Field(
        default_factory=list
    )


class DiscordMessageRemove(BaseModel):
    channel_id: int
    message_id: int


class DiscordMessageResponse(BaseModel):
    channel_id: int
    message_id: int


# ============================================================
# COMMAND
# ============================================================

class CommandArgument(BaseModel):
    name: str
    type: str = "str"
    required: bool = True
    description: str = ""
    default: Any = None


class Command(BaseModel):
    name: str
    description: str
    service: str = ""
    group: str = ""
    tag: str

    permission: str = ""

    ephemeral: bool = True

    args: list[CommandArgument] = Field(
        default_factory=list
    )


class ExecutedArgs(BaseModel):
    name: str
    value: str
    type: str
    is_required: bool = False


class ExecutedCommand(BaseModel):
    service: str
    tag: str

    user: User
    guild: Guild
    channel: Channel

    entity_id: str = ""

    reply_to: str = ""

    entity_type: InteractionType = (
        InteractionType.CONNECT
    )

    args: list[ExecutedArgs] = Field(
        default_factory=list
    )


class ExecutedCommandResponse(BaseModel):
    """
    Ответ после выполнения команды.

    Старый API:
        message
        embeds
        buttons

    Components V2:
        containers
    """

    message: str = ""

    ephemeral: bool = True

    # Старые Embed
    embeds: list[Embed] = Field(
        default_factory=list
    )

    # Старые кнопки
    buttons: list[ComponentButton] = Field(
        default_factory=list
    )

    # Components V2
    containers: list[Container] = Field(
        default_factory=list
    )

    is_final: bool = False


# ============================================================
# VOICE
# ============================================================

class VoiceChannelConnectInteraction(BaseModel):
    channel_id: int

    interaction_type: InteractionType = (
        InteractionType.CONNECT
    )


class VoiceChannelUserConnectionEvent(BaseModel):
    user: User

    after_channel: Channel | None = None
    before_channel: Channel | None = None

    guild: Guild | None = None

    action: VoiceChannelUserConnectionType


class VoiceChannel(BaseModel):
    channel: Channel | None
    guild: Guild | None = None


class VoiceChannelPlaySound(VoiceChannel):
    sound: str
    track_id: str

    before_options: str | None = None
    options: str | None = None


class VoiceConnectionStatus(VoiceChannel):
    connected: bool

    playing: bool = False
    paused: bool = False


class VoiceConnectionRequest(VoiceChannel):
    interaction_type: InteractionType = (
        InteractionType.CONNECT
    )


class VoiceConnectionResponse(VoiceConnectionStatus):
    success: bool = True
    error: str | None = None


class VoicePlayingCallback(BaseModel):
    success: bool = True
    message: str | None = None


class SoundControl(BaseModel):
    guild_id: int
    action: SoundAction