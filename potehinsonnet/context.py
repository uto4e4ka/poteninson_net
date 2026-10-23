"""Что хост даёт плагину при запуске: папку данных, настройки, адрес NATS, токен.

Хост передаёт всё переменными окружения. Без хоста (разработка) работают значения по умолчанию:
данные — ./data рядом с плагином, настройки — ./settings.json, NATS — localhost.

    PLUGIN_DATA_DIR       папка данных: переживает обновления и откаты плагина
    PLUGIN_SETTINGS_FILE  JSON с настройками, которые владелец задал в панели
    PLUGIN_TOKEN          токен плагина: им плагин представляется боту
    NATS_URL              адрес NATS
"""
import json
import os
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from potehinsonnet.manifest import ManifestError, PluginManifest, load_manifest
from potehinsonnet.storage import DataDir

DEFAULT_NATS_URL = "nats://localhost:4222"


@dataclass
class PluginContext:
    root: Path                       # корень плагина (там plugin.toml)
    manifest: PluginManifest
    data_dir: Path
    settings: dict[str, Any] = field(default_factory=dict)
    nats_url: str = DEFAULT_NATS_URL
    token: str = ""

    @cached_property
    def data(self) -> DataDir:
        """Файлы данных плагина: ctx.data.collection("pets.json", Pet, key="pet_id"), ctx.data.document(...)."""
        return DataDir(self.data_dir)

    @property
    def assets_dir(self) -> Path:
        """Файлы, которые едут вместе с кодом (стандартные картинки, звуки) — только для чтения."""
        return self.root / "assets"

    @classmethod
    def load(cls, root: str | Path, env: dict[str, str] | None = None) -> "PluginContext":
        """Собрать контекст: манифест из root, остальное — из окружения (env) или значения для разработки."""
        env = os.environ if env is None else env
        root = Path(root).resolve()
        manifest = load_manifest(root)
        data_dir = Path(env.get("PLUGIN_DATA_DIR") or root / "data")
        data_dir.mkdir(parents=True, exist_ok=True)
        settings_file = Path(env.get("PLUGIN_SETTINGS_FILE") or root / "settings.json")
        return cls(
            root=root, manifest=manifest, data_dir=data_dir,
            settings=read_settings(manifest, settings_file),
            nats_url=env.get("NATS_URL") or DEFAULT_NATS_URL,
            token=env.get("PLUGIN_TOKEN", ""),
        )


def read_settings(manifest: PluginManifest, path: Path) -> dict[str, Any]:
    """Настройки из файла поверх значений по умолчанию из манифеста. Обязательной нет — ManifestError."""
    saved: dict[str, Any] = {}
    if path.is_file():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ManifestError(f"{path}: ошибка в JSON — {e}") from e
    settings = {}
    for key, spec in manifest.settings.items():
        value = saved.get(key, spec.default)
        if value in (None, "") and spec.required:
            raise ManifestError(f"{manifest.name}: не задана обязательная настройка «{spec.label}» ({key})")
        settings[key] = value
    return settings
