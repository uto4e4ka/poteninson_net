"""Сборка zip плагина: версия, что попадает в архив, а что нет."""
import zipfile

import pytest

from potehinsonnet.pack import bump, main, pack


def make_plugin(root, version="1.2.3", pyproject_version="1.2.3"):
    (root / "demo_plugin").mkdir(parents=True)
    (root / "plugin.toml").write_text(f'[plugin]\nname = "demo_plugin"\nlabel = "Демо"\nversion = "{version}"\n\n'
                                      f'[runtime]\nentry = "demo_plugin.main:create_plugin"\n', encoding="utf-8")
    (root / "pyproject.toml").write_text(f'[project]\nname = "demo"\nversion = "{pyproject_version}"\n'
                                         f'dependencies = ["x (>=1.0.0)"]\n', encoding="utf-8")
    (root / "demo_plugin" / "main.py").write_text("x = 1\n")
    (root / "data").mkdir()
    (root / "data" / "pets.json").write_text("[]")
    (root / "data" / "pets.json.broken-2026").write_text("[")
    (root / "data" / "a.json.tmp").write_text("{}")
    (root / "settings.json").write_text('{"api_key": "секрет"}')
    (root / ".env").write_text("TOKEN=1")
    (root / ".venv" / "lib").mkdir(parents=True)
    (root / ".venv" / "lib" / "x.py").write_text("")
    return root


@pytest.mark.parametrize("part, expected", [("patch", "1.2.4"), ("minor", "1.3.0"), ("major", "2.0.0")])
def test_bump(part, expected):
    assert bump("1.2.3", part) == expected


def test_pack_with_bump_skips_secrets_and_junk(tmp_path):
    root = make_plugin(tmp_path / "demo")
    archive = pack(root, bump_part="minor")

    assert archive == (root / "dist" / "demo-1.3.0.zip").resolve()
    assert 'version = "1.3.0"' in (root / "plugin.toml").read_text(encoding="utf-8")
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "1.3.0"' in pyproject and 'x (>=1.0.0)' in pyproject           # остальное не тронуто
    names = sorted(zipfile.ZipFile(archive).namelist())
    assert names == ["data/pets.json", "demo_plugin/main.py", "plugin.toml", "pyproject.toml"]


def test_pack_without_data_and_different_pyproject_version(tmp_path):
    root = make_plugin(tmp_path / "demo", pyproject_version="0.1.0")
    archive = pack(root, bump_part="patch", with_data=False, out=tmp_path / "out")

    assert archive.parent == (tmp_path / "out").resolve() and archive.name == "demo-1.2.4.zip"
    assert 'version = "0.1.0"' in (root / "pyproject.toml").read_text(encoding="utf-8")   # чужую версию не трогаем
    assert not any(n.startswith("data/") for n in zipfile.ZipFile(archive).namelist())


def test_old_archives_in_dist_are_not_packed(tmp_path):
    root = make_plugin(tmp_path / "demo")
    pack(root)
    second = pack(root, bump_part="patch")
    assert not any(n.startswith("dist/") for n in zipfile.ZipFile(second).namelist())


def test_cli_without_plugin_toml(tmp_path):
    with pytest.raises(SystemExit, match="нет plugin.toml"):
        main([str(tmp_path)])
