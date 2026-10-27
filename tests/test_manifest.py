"""Манифест плагина, контекст от хоста и запуск по манифесту."""
import json
import sys
import textwrap

import pytest

from potehinsonnet import ManifestError, Plugin, PluginContext, load_manifest
from potehinsonnet.manifest import version_matches
from potehinsonnet.run import build
from potehinsonnet.testing import FakeNats

MANIFEST = """
[plugin]
name = "demo_plugin"
label = "Демо"
description = "Для тестов"
version = "1.2.3"
author = "me"

[runtime]
entry = "demo_plugin.main:create_plugin"
python = ">=3.10"

[permissions]
discord = ["send_message", "members"]
commands = true

[settings.greeting]
label = "Приветствие"
default = "Привет"

[settings.api_key]
label = "Ключ"
secret = true
required = true
"""

ENTRY = """
from potehinsonnet import Plugin

def create_plugin(ctx):
    plugin = Plugin.from_context(ctx, nats=ctx.settings.pop("_nats"))
    plugin.greeting = ctx.settings["greeting"]
    return plugin
"""


def make_plugin(tmp_path, manifest=MANIFEST, settings=None):
    (tmp_path / "plugin.toml").write_text(textwrap.dedent(manifest), encoding="utf-8")
    package = tmp_path / "demo_plugin"
    package.mkdir(exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "main.py").write_text(ENTRY, encoding="utf-8")
    if settings is not None:
        (tmp_path / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    return tmp_path


def test_manifest_is_read_and_becomes_service(tmp_path):
    manifest = load_manifest(make_plugin(tmp_path))

    service = manifest.service()
    assert (service.name, service.label, service.version, service.author) == ("demo_plugin", "Демо", "1.2.3", "me")
    assert manifest.permissions.discord == ["members", "send_message"]
    assert manifest.permissions.commands and not manifest.permissions.panel


@pytest.mark.parametrize("broken, message", [
    ('name = "demo_plugin"', 'name = "Demo-Plugin"'),                                       # плохое имя
    ('entry = "demo_plugin.main:create_plugin"', 'entry = "main:create_plugin"'),           # не пакетом
    ('discord = ["send_message", "members"]', 'discord = ["send_mesage"]'),                 # опечатка в праве
])
def test_bad_manifest_is_rejected(tmp_path, broken, message):
    with pytest.raises(ManifestError):
        load_manifest(make_plugin(tmp_path, MANIFEST.replace(broken, message)))


def test_missing_manifest(tmp_path):
    with pytest.raises(ManifestError, match="Нет plugin.toml"):
        load_manifest(tmp_path)


def test_context_from_host_environment(tmp_path):
    (tmp_path / "code").mkdir()
    root = make_plugin(tmp_path / "code")   # код и данные — в разных местах, как у хоста
    settings = tmp_path / "host-settings.json"
    settings.write_text(json.dumps({"api_key": "secret"}), encoding="utf-8")
    env = {"PLUGIN_DATA_DIR": str(tmp_path / "data"), "PLUGIN_SETTINGS_FILE": str(settings),
           "PLUGIN_TOKEN": "tok", "NATS_URL": "nats://nats:4222"}

    ctx = PluginContext.load(root, env)

    assert ctx.data_dir == tmp_path / "data" and ctx.data_dir.is_dir()
    assert ctx.settings == {"greeting": "Привет", "api_key": "secret"}   # значение по умолчанию + из файла
    assert (ctx.token, ctx.nats_url) == ("tok", "nats://nats:4222")


def test_context_for_development_uses_plugin_folder(tmp_path):
    ctx = PluginContext.load(make_plugin(tmp_path, settings={"api_key": "k", "greeting": "Хай"}), env={})

    assert ctx.data_dir == tmp_path / "data"
    assert ctx.settings["greeting"] == "Хай" and ctx.nats_url == "nats://localhost:4222"


def test_required_setting_missing(tmp_path):
    with pytest.raises(ManifestError, match="Ключ"):
        PluginContext.load(make_plugin(tmp_path), env={})


async def test_build_imports_entry_and_returns_plugin(tmp_path):
    ctx = PluginContext.load(make_plugin(tmp_path, settings={"api_key": "k"}), env={})
    ctx.settings["_nats"] = FakeNats().client()

    plugin = await build(ctx)

    assert isinstance(plugin, Plugin)
    assert plugin.service.name == "demo_plugin" and plugin.context is ctx
    assert plugin.greeting == "Привет"


@pytest.mark.parametrize("version, spec, ok", [
    ("0.10.0", ">=0.10,<0.11", True),
    ("0.9.5", ">=0.10,<0.11", False),
    ("3.14.0", ">=3.14", True),
    ("1.2", "==1.2.0", True),
    ("1.2.1", "!=1.2.1", False),
])
def test_version_matches(version, spec, ok):
    assert version_matches(version, spec) is ok


def test_incompatible_library_version(tmp_path, monkeypatch):
    manifest = load_manifest(make_plugin(tmp_path, MANIFEST.replace('python = ">=3.10"',
                                                                     'python = ">=3.10"\npotehinsonnet = ">=99"')))
    monkeypatch.setattr("potehinsonnet.manifest.installed_version", lambda name: "0.10.0")
    with pytest.raises(ManifestError, match="potehinsonnet"):
        manifest.check_compatible()


@pytest.mark.parametrize("main_code, expected", [
    ("from idlelib_no_such import window\n", "не нашёлся модуль «idlelib_no_such» — "),   # сломанный импорт внутри
    ("raise RuntimeError('конфиг битый')\n", "RuntimeError: конфиг битый"),
    ("x = 1\n", "нет функции create_plugin"),
])
async def test_build_explains_where_import_failed(tmp_path, main_code, expected):
    root = make_plugin(tmp_path, settings={"api_key": "k"})
    (root / "demo_plugin" / "main.py").write_text(main_code, encoding="utf-8")
    for name in [m for m in sys.modules if m.startswith("demo_plugin")]:
        del sys.modules[name]
    ctx = PluginContext.load(root, env={})

    with pytest.raises(ManifestError) as error:
        await build(ctx)
    assert expected in str(error.value)
    if "не нашёлся" in expected:
        assert "main.py, строка 1" in str(error.value)


async def test_build_missing_entry_module(tmp_path):
    root = make_plugin(tmp_path, MANIFEST.replace("demo_plugin.main:create_plugin", "demo_plugin.nope:create_plugin"),
                       settings={"api_key": "k"})
    with pytest.raises(ManifestError, match="не найден модуль demo_plugin.nope"):
        await build(PluginContext.load(root, env={}))


async def test_error_points_to_plugin_line_not_library(tmp_path):
    # Как с idlelib на сервере: импорт стандартного модуля падает уже внутри него
    root = make_plugin(tmp_path, settings={"api_key": "k"})
    (root / "demo_plugin" / "main.py").write_text("import json\nimport demo_plugin.broken\n", encoding="utf-8")
    (root / "demo_plugin" / "broken.py").write_text("x = 1\nfrom json import no_such_name\n", encoding="utf-8")
    for name in [m for m in sys.modules if m.startswith("demo_plugin")]:
        del sys.modules[name]

    with pytest.raises(ManifestError) as error:
        await build(PluginContext.load(root, env={}))
    message = str(error.value)
    assert "ImportError" in message and "broken.py, строка 2: from json import no_such_name" in message
