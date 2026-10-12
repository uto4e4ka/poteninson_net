"""Протокол веб-панели: запросы панели к боту и плагинам через NATS.

Все темы — request/reply. Бот отвечает на panel.plugins.*, panel.guild.*, panel.permissions.*,
sound core — на panel.music.* и panel.greetings.*.
"""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# ============================================================
# ТЕМЫ
# ============================================================

PLUGINS_LIST = "panel.plugins.list"

GUILD_ROLES = "panel.guild.roles"
GUILD_MEMBERS_GET = "panel.guild.members.get"
GUILD_MEMBERS_SEARCH = "panel.guild.members.search"

PERMISSIONS_LIST = "panel.permissions.list"
PERMISSIONS_ADD = "panel.permissions.add"
PERMISSIONS_REMOVE = "panel.permissions.remove"

GREETINGS_LIST = "panel.greetings.list"
GREETINGS_SET = "panel.greetings.set"
GREETINGS_REMOVE = "panel.greetings.remove"

MUSIC_STATE = "panel.music.state"
MUSIC_CONTROL = "panel.music.control"


# ============================================================
# ОБЩЕЕ
# ============================================================

class GuildRequest(BaseModel):
    guild_id: int


class PanelResult(BaseModel):
    """Ответ на действие: успех или понятная пользователю ошибка."""

    ok: bool = True
    message: str = ""


# ============================================================
# ПЛАГИНЫ
# ============================================================

class PluginInfo(BaseModel):
    name: str
    label: str = ""
    description: str = ""
    author: str = ""
    version: str = ""
    status: str = ""
    last_seen: datetime | None = None


class PluginList(BaseModel):
    plugins: list[PluginInfo] = Field(default_factory=list)


# ============================================================
# СЕРВЕР DISCORD
# ============================================================

class RoleInfo(BaseModel):
    id: int
    name: str
    color: int = 0


class RoleList(BaseModel):
    roles: list[RoleInfo] = Field(default_factory=list)


class MemberInfo(BaseModel):
    id: int
    name: str
    display_name: str = ""
    avatar_url: str | None = None


class MembersGetRequest(GuildRequest):
    ids: list[int] = Field(default_factory=list)


class MembersSearchRequest(GuildRequest):
    query: str
    limit: int = 10


class MemberList(BaseModel):
    members: list[MemberInfo] = Field(default_factory=list)


# ============================================================
# ПРАВА
# ============================================================

class PermissionTarget(str, Enum):
    ROLE = "ROLE"
    USER = "USER"


class PermissionLinkInfo(BaseModel):
    type: PermissionTarget
    id: int
    name: str = ""


class PermissionRule(BaseModel):
    permission: str
    links: list[PermissionLinkInfo] = Field(default_factory=list)


class PermissionList(BaseModel):
    rules: list[PermissionRule] = Field(default_factory=list)


class PermissionChange(GuildRequest):
    permission: str
    type: PermissionTarget
    target_id: int


# ============================================================
# ПРИВЕТСТВИЯ
# ============================================================

class GreetingInfo(BaseModel):
    user_id: int
    sound_url: str
    disabled: bool = False


class GreetingList(BaseModel):
    default_sound_url: str = ""
    greetings: list[GreetingInfo] = Field(default_factory=list)


class GreetingSet(GuildRequest):
    user_id: int
    sound_url: str
    disabled: bool = False


class GreetingRemove(GuildRequest):
    user_id: int


# ============================================================
# МУЗЫКА
# ============================================================

class MusicAction(str, Enum):
    PAUSE = "pause"
    RESUME = "resume"
    SKIP = "skip"
    PREVIOUS = "previous"
    SHUFFLE = "shuffle"
    STOP = "stop"


class TrackInfo(BaseModel):
    name: str
    author: str = ""
    url: str = ""
    icon_url: str = ""
    duration: float = 0


class MusicState(BaseModel):
    playing: bool = False
    track: TrackInfo | None = None
    is_paused: bool = False
    is_shuffled: bool = False
    has_previous: bool = False
    can_shuffle: bool = False
    queue: list[str] = Field(default_factory=list)   # следующие треки
    current_index: int = -1


class MusicControl(GuildRequest):
    action: MusicAction
