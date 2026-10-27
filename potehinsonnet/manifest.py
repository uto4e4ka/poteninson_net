"""Манифест плагина — plugin.toml в корне плагина. Единственное место, где записаны имя, версия и права.

    [plugin]
    name = "potehinson_tamagochi"        # id: латиница, цифры, _
    label = "Potehinson Tamagochi"
    description = "Вырасти своего потешку"
    version = "0.4.2"
    author = "Uto4ka404"
    icon = "icon.png"                    # путь от корня плагина, необязательно

    [runtime]
    entry = "potehinson_tamagochi.main:create_plugin"   # модуль:функция, получает PluginContext
    python = ">=3.14"
    potehinsonnet = ">=0.10,<0.11"

    [permissions]                        # что плагин просит у бота; владелец подтверждает при установке
    discord = ["send_message", "edit_message", "members"]
    commands = true
    panel = true

    [settings.api_key]                   # что владелец заполняет в панели при установке
    label = "Ключ API"
    secret = true
"""
import re
import sys
import tomllib
from importlib.metadata import PackageNotFoundError, version as installed_version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from potehinsonnet.net_models.system_models import Service

MANIFEST_FILE = "plugin.toml"
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")

# Что плагин может попросить у бота. Бот проверяет это на каждом запросе
DISCORD_PERMISSIONS = {
    "send_message",     # писать в каналы
    "edit_message",     # править и удалять свои сообщения
    "members",          # видеть участников сервера
    "roles",            # видеть роли
    "channels",         # видеть каналы
    "voice",            # голосовые каналы: подключаться, играть звук
}


class ManifestError(ValueError):
    """plugin.toml не найден или заполнен неправильно."""


class PluginInfo(BaseModel):
    name: str
    label: str
    description: str = ""
    version: str
    author: str = ""
    icon: str = ""
    site: str = ""

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        if not NAME_PATTERN.match(value):
            raise ValueError("name — латиница в нижнем регистре, цифры и _, начинается с буквы, до 64 символов")
        return value

    @field_validator("version")
    @classmethod
    def _version(cls, value: str) -> str:
        if not re.fullmatch(r"\d+(\.\d+){0,2}([-+.].*)?", value):
            raise ValueError("version — как 1.2.3")
        return value


class Runtime(BaseModel):
    entry: str                       # «пакет.модуль:функция»
    python: str = ""                 # «>=3.14»
    potehinsonnet: str = ""          # «>=0.10,<0.11»

    @field_validator("entry")
    @classmethod
    def _entry(cls, value: str) -> str:
        module, _, func = value.partition(":")
        if not module or not func or not all(part.isidentifier() for part in [*module.split("."), func]):
            raise ValueError("entry — «пакет.модуль:функция», например my_plugin.main:create_plugin")
        if "." not in module:
            raise ValueError("код плагина — пакетом: entry = «my_plugin.main:create_plugin», а не «main:…»")
        return value


class Permissions(BaseModel):
    discord: list[str] = Field(default_factory=list)
    commands: bool = False           # регистрировать слэш-команды
    panel: bool = False              # свои страницы в веб-панели

    @field_validator("discord")
    @classmethod
    def _discord(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - DISCORD_PERMISSIONS)
        if unknown:
            raise ValueError(f"неизвестные права: {', '.join(unknown)}; есть: {', '.join(sorted(DISCORD_PERMISSIONS))}")
        return sorted(set(value))


class SettingSpec(BaseModel):
    """Одна настройка, которую владелец задаёт в панели при установке."""
    label: str
    description: str = ""
    type: Literal["text", "number", "bool"] = "text"
    secret: bool = False             # ключи и токены: в панели не показываются после сохранения
    required: bool = False
    default: str | float | bool | None = None


class PluginManifest(BaseModel):
    plugin: PluginInfo
    runtime: Runtime
    permissions: Permissions = Field(default_factory=Permissions)
    settings: dict[str, SettingSpec] = Field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.plugin.name

    def service(self) -> Service:
        """Описание для бота и панели — то, что раньше писали в коде как Service(...)."""
        info = self.plugin
        return Service(type="plugin", name=info.name, label=info.label, description=info.description,
                       author=info.author, version=info.version, icon=info.icon, site=info.site)

    def check_compatible(self) -> None:
        """Подходит ли плагину этот Python и эта версия potehinsonnet. Нет — ManifestError."""
        python = ".".join(map(str, sys.version_info[:3]))
        if self.runtime.python and not version_matches(python, self.runtime.python):
            raise ManifestError(f"{self.name}: нужен Python {self.runtime.python}, а запущен {python}")
        if self.runtime.potehinsonnet:
            try:
                library = installed_version("potehinsonnet")
            except PackageNotFoundError:
                return  # запуск из исходников библиотеки — версию не проверить
            if not version_matches(library, self.runtime.potehinsonnet):
                raise ManifestError(
                    f"{self.name}: нужна potehinsonnet {self.runtime.potehinsonnet}, а стоит {library}")


def load_manifest(root: str | Path) -> PluginManifest:
    """Прочитать plugin.toml из корня плагина."""
    path = Path(root) / MANIFEST_FILE
    if not path.is_file():
        raise ManifestError(f"Нет {MANIFEST_FILE} в {Path(root).resolve()}")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ManifestError(f"{path}: ошибка в TOML — {e}") from e
    try:
        return PluginManifest.model_validate(data)
    except ValueError as e:
        raise ManifestError(f"{path}: {e}") from e


# ----------------------------------------------------------------------
# Версии: «>=0.10,<0.11» — без лишних зависимостей
# ----------------------------------------------------------------------

def _parse(value: str) -> tuple[int, ...]:
    numbers = re.match(r"\d+(\.\d+)*", value.strip())
    if not numbers:
        raise ManifestError(f"Не понимаю версию «{value}»")
    return tuple(int(n) for n in numbers.group(0).split("."))


def _compare(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    width = max(len(a), len(b))
    a, b = a + (0,) * (width - len(a)), b + (0,) * (width - len(b))
    return (a > b) - (a < b)


def version_matches(version: str, spec: str) -> bool:
    """Подходит ли версия под условия через запятую: >=, <=, >, <, ==, !=."""
    current = _parse(version)
    checks = {">=": lambda c: c >= 0, "<=": lambda c: c <= 0, "==": lambda c: c == 0,
              "!=": lambda c: c != 0, ">": lambda c: c > 0, "<": lambda c: c < 0}
    for part in filter(None, (p.strip() for p in spec.split(","))):
        operator = next((op for op in (">=", "<=", "==", "!=", ">", "<") if part.startswith(op)), "==")
        target = part.removeprefix(operator) if part.startswith(operator) else part
        if not checks[operator](_compare(current, _parse(target))):
            return False
    return True
