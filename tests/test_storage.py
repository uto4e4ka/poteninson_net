"""Данные плагина в JSON: ctx.data, документ, коллекция, атомарность, битые файлы, кэш."""
import json
import os
import textwrap
from datetime import datetime

import pytest
from pydantic import BaseModel

from potehinsonnet import PluginContext
from potehinsonnet.storage import DataDir, JsonCollection, JsonDocument, StorageError


class Pet(BaseModel):
    pet_id: str
    name: str
    level: int = 1
    born: datetime | None = None


class Settings(BaseModel):
    bonus: int = 150
    names: list[str] = []


def test_collection_put_get_delete_keeps_order(tmp_path):
    pets = JsonCollection(tmp_path / "pets.json", Pet, key="pet_id")
    assert pets.all() == [] and pets.get("a") is None and not pets.path.exists()

    pets.put(Pet(pet_id="a", name="Кот"))
    pets.put(Pet(pet_id="b", name="Пёс", born=datetime(2026, 10, 1, 12, 0)))
    pets.put(Pet(pet_id="a", name="Кот", level=5))                         # замена на том же месте
    assert [(p.pet_id, p.level) for p in pets.all()] == [("a", 5), ("b", 1)]
    assert pets.get("b").born == datetime(2026, 10, 1, 12, 0)              # datetime ↔ ISO-строка

    saved = json.loads(pets.path.read_text(encoding="utf-8"))
    assert saved[1]["name"] == "Пёс" and "Пёс" in pets.path.read_text(encoding="utf-8")   # кириллица как есть
    assert pets.delete("a") and not pets.delete("nope")
    assert [p.pet_id for p in pets.all()] == ["b"]
    assert pets.filter(lambda p: p.level > 0)[0].name == "Пёс"
    assert not list(tmp_path.glob("*.tmp"))                                 # временный файл не остался


def test_document_default_save_update(tmp_path):
    doc = JsonDocument(tmp_path / "s.json", Settings)
    assert doc.load() == Settings() and not doc.exists()

    doc.save(Settings(bonus=200))
    assert doc.load().bonus == 200
    doc.update(lambda s: s.names.append("Вася"))                            # можно менять на месте…
    doc.update(lambda s: s.model_copy(update={"bonus": 300}))              # …или вернуть новый
    assert doc.load() == Settings(bonus=300, names=["Вася"])

    custom = JsonDocument(tmp_path / "other.json", Settings, default=lambda: Settings(bonus=1))
    assert custom.load().bonus == 1


def test_changes_without_save_do_not_leak(tmp_path):
    pets = JsonCollection(tmp_path / "pets.json", Pet, key="pet_id")
    pets.put(Pet(pet_id="a", name="Кот"))
    pet = pets.get("a")
    pet.level = 99                                                          # поменяли, но не сохранили
    assert pets.get("a").level == 1


def test_outside_edit_is_picked_up(tmp_path):
    pets = JsonCollection(tmp_path / "pets.json", Pet, key="pet_id")
    pets.put(Pet(pet_id="a", name="Кот"))
    assert pets.get("a").name == "Кот"                                      # теперь в кэше

    pets.path.write_text('[{"pet_id": "a", "name": "Правка из панели"}]', encoding="utf-8")
    stat = pets.path.stat()
    os.utime(pets.path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))   # гарантированно другое время
    assert pets.get("a").name == "Правка из панели"


@pytest.mark.parametrize("content, reason", [
    ('[{"pet_id": "a", "name": ', "не читается как JSON"),                 # обрезан при сбое
    ('[{"pet_id": "a"}]', "не подходит под список Pet"),                   # нет обязательного поля
])
def test_broken_file_is_set_aside_not_overwritten(tmp_path, content, reason, caplog):
    path = tmp_path / "pets.json"
    path.write_text(content, encoding="utf-8")
    pets = JsonCollection(path, Pet, key="pet_id")

    with pytest.raises(StorageError, match=reason):
        pets.all()

    [broken] = tmp_path.glob("pets.json.broken-*")
    assert broken.read_text(encoding="utf-8") == content                    # исходник цел
    assert not path.exists() and "отложен" in caplog.text


def test_data_dir_paths_stay_inside(tmp_path):
    data = DataDir(tmp_path / "data")
    assert data.path("guilds/1.json") == (tmp_path / "data" / "guilds" / "1.json").resolve()
    for bad in ("../code/main.py", "guilds/../../x.json", str(tmp_path / "abs.json"), "."):
        with pytest.raises(StorageError, match="только внутри"):
            data.path(bad)

    first = data.collection("pets.json", Pet, key="pet_id")
    assert data.collection("pets.json", Pet, key="pet_id") is first        # один объект — один кэш
    data.document("guilds/1.json", Settings).save(Settings())
    assert (tmp_path / "data" / "guilds" / "1.json").exists()               # папки создаются сами


def test_context_data_points_to_plugin_data_dir(tmp_path):
    (tmp_path / "plugin.toml").write_text(textwrap.dedent("""
        [plugin]
        name = "demo_plugin"
        label = "Демо"
        version = "1.0.0"

        [runtime]
        entry = "demo_plugin.main:create_plugin"
    """), encoding="utf-8")
    ctx = PluginContext.load(tmp_path, env={"PLUGIN_DATA_DIR": str(tmp_path / "host-data")})

    ctx.data.collection("pets.json", Pet, key="pet_id").put(Pet(pet_id="a", name="Кот"))
    assert (tmp_path / "host-data" / "pets.json").exists()
    assert ctx.data is ctx.data
