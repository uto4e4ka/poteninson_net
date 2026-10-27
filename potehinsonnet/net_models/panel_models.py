"""Протокол веб-панели: запросы панели к боту через NATS.

Все темы — request/reply, отвечает бот. Страницы плагинов — отдельный протокол, см. panel_ui.
Темы panel.guild.* может спрашивать и любой плагин, например чтобы показать имена участников.
"""
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from potehinsonnet.net_models.panel_ui import FileRef, PageScope, PanelPageInfo

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

# Установка и запуск плагинов — хост внутри бота
HOST_LIST = "panel.host.list"
HOST_INSTALL = "panel.host.install"
HOST_CONTROL = "panel.host.control"
HOST_LOGS = "panel.host.logs"
HOST_UPLOAD = "panel.host.upload"      # zip с плагином — по кускам, потом HOST_INSTALL с source="zip"
BOT_OWNERS = "panel.bot.owners"        # владельцы бота (приложения Discord) — только они управляют плагинами
BOT_GUILDS = "panel.bot.guilds"        # серверы бота и может ли этот человек ими управлять
PAGE_SCOPES = "panel.pages.scopes"     # где показывать страницы плагинов: переопределения владельца бота
PAGE_SCOPE_SET = "panel.pages.scope.set"


# ============================================================
# ОБЩЕЕ
# ============================================================

class GuildRequest(BaseModel):
    guild_id: int


class PanelResult(BaseModel):
    """Ответ на действие: успех или понятная пользователю ошибка."""

    ok: bool = True
    message: str = ""
    # Файл, который панель сразу отдаст браузеру: положите его через plugin.files.put(...)
    download: FileRef | None = None


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
# УСТАНОВКА ПЛАГИНОВ (хост внутри бота)
# ============================================================

class InstalledPlugin(BaseModel):
    """Плагин, который поставил и запускает хост."""

    name: str
    label: str = ""
    description: str = ""
    version: str = ""
    source: Literal["git", "path", "zip"] = "path"
    url: str = ""                    # git — откуда клонировали; path — папка на сервере; zip — имя архива
    ref: str = ""                    # git — ветка или тег
    state: Literal["running", "stopped", "crashed", "starting"] = "stopped"
    enabled: bool = True             # поднимать при старте бота и после падения
    pid: int | None = None
    restarts: int = 0                # сколько раз подряд падал
    permissions: list[str] = Field(default_factory=list)   # что плагин просит у бота — по-человечески
    error: str = ""                  # последняя ошибка запуска


class InstalledList(BaseModel):
    plugins: list[InstalledPlugin] = Field(default_factory=list)


class OwnersResponse(BaseModel):
    """Владельцы бота: владелец приложения Discord или все участники его команды."""

    ids: list[int] = Field(default_factory=list)


class GuildsRequest(BaseModel):
    user_id: int                     # для кого: can_manage — может ли он управлять сервером


class GuildInfo(BaseModel):
    id: int
    name: str
    icon_url: str | None = None
    can_manage: bool = False         # владелец сервера, «Администратор» или «Управлять сервером»; владелец бота — везде


class GuildList(BaseModel):
    guilds: list[GuildInfo] = Field(default_factory=list)


# Видимость страницы: как решил плагин, или куда переложил владелец бота; hidden — нигде
PageVisibility = Literal["bot", "guild", "hidden"]


def page_key(plugin: str, page: str) -> str:
    return f"{plugin}/{page}"


class PageScopes(BaseModel):
    """Переопределения владельца бота: ключ page_key → куда. Чего нет — там, где решил плагин."""

    scopes: dict[str, PageVisibility] = Field(default_factory=dict)

    def effective(self, plugin: str, page: PanelPageInfo) -> PageVisibility:
        return self.scopes.get(page_key(plugin, page.id), page.scope)


class PageScopeChange(BaseModel):
    actor_id: int | None = None      # бот проверяет, что это владелец
    plugin: str
    page: str
    scope: PageVisibility | None = None   # None — вернуть как решил плагин


class InstallRequest(BaseModel):
    actor_id: int | None = None      # кто из панели просит — бот проверяет, что это владелец
    source: Literal["git", "path", "zip"]
    url: str = ""                    # git: https://github.com/…; path: папка на сервере бота; zip: upload_id
    ref: str = ""                    # git: ветка или тег (пусто — по умолчанию)


class UploadChunk(BaseModel):
    """Кусок загружаемого zip: NATS не пропустит большой файл одним сообщением."""

    actor_id: int | None = None
    upload_id: str                   # одинаковый у всех кусков одного файла
    index: int                       # с 0
    total: int
    filename: str = ""
    data: str                        # base64


class ControlRequest(BaseModel):
    actor_id: int | None = None
    name: str
    action: Literal["start", "stop", "restart", "remove", "enable", "disable"]
    keep_data: bool = True           # remove: оставить данные плагина


class LogsRequest(BaseModel):
    actor_id: int | None = None
    name: str
    lines: int = 200


class LogsResponse(BaseModel):
    lines: list[str] = Field(default_factory=list)


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
