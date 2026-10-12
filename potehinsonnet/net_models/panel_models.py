"""Протокол веб-панели: запросы панели к боту через NATS.

Все темы — request/reply, отвечает бот. Страницы плагинов — отдельный протокол, см. panel_ui.
Темы panel.guild.* может спрашивать и любой плагин, например чтобы показать имена участников.
"""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from potehinsonnet.net_models.panel_ui import PanelPageInfo

# ============================================================
# ТЕМЫ
# ============================================================

PLUGINS_LIST = "panel.plugins.list"

GUILD_ROLES = "panel.guild.roles"
GUILD_CHANNELS = "panel.guild.channels"
GUILD_MEMBERS_GET = "panel.guild.members.get"
GUILD_MEMBERS_SEARCH = "panel.guild.members.search"

PERMISSIONS_LIST = "panel.permissions.list"
PERMISSIONS_ADD = "panel.permissions.add"
PERMISSIONS_REMOVE = "panel.permissions.remove"


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
    pages: list[PanelPageInfo] = Field(default_factory=list)


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


class ChannelInfo(BaseModel):
    id: int
    name: str
    type: str            # "text" или "voice"
    category: str = ""


class ChannelList(BaseModel):
    channels: list[ChannelInfo] = Field(default_factory=list)


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
