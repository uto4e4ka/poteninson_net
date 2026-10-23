"""Данные плагина в JSON-файлах: надёжно и без своих _read/_write в каждом плагине.

    pets = ctx.data.collection("pets.json", Pet, key="pet_id")     # → <data_dir>/pets.json
    pets.put(pet); pets.get("abc"); pets.all(); pets.delete("abc")

    rewards = ctx.data.document("rewards.json", RewardSettings)    # нет файла → RewardSettings()
    settings = rewards.load(); rewards.save(settings)

Что делается само:
- данные проверяются моделью pydantic при чтении и сериализуются ею при записи;
- запись атомарная (временный файл → replace): при сбое файл либо старый, либо новый;
- битый файл не затирается: он переименовывается в <имя>.broken-<время>, в лог — предупреждение,
  а чтение бросает StorageError, чтобы плагин не продолжил работу с «пустыми» данными;
- кэш: пока файл не менялся (время и размер те же), с диска не читаем; изменили снаружи
  (редактор в панели, руками) — перечитаем. Каждое чтение отдаёт новые объекты: правка полученного
  объекта без save() в данных не появится.

Сырой JSON без моделей (свой формат, постепенный переход старого кода) — ctx.data.file("x.json"):
read() → данные или None, write(данные) — с той же атомарностью, кэшем и защитой от битых файлов.
"""
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

log = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)


class StorageError(Exception):
    """Файл данных испорчен или имя выходит за папку данных."""


class JsonFile:
    """Один JSON-файл как есть, без моделей: атомарная запись, кэш по времени изменения, битый — в сторону.

    read() каждый раз отдаёт новые объекты: правка полученного словаря на месте ни кэш, ни файл не меняет.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._cache: tuple[tuple[int, int], str] | None = None   # (mtime_ns, размер), текст файла
        self._lock = threading.Lock()

    def read(self) -> Any | None:
        """Разобранный JSON или None, если файла нет."""
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            self._cache = None
            return None
        stamp = (stat.st_mtime_ns, stat.st_size)
        if self._cache is None or self._cache[0] != stamp:
            try:
                text = self.path.read_text(encoding="utf-8")
            except UnicodeDecodeError as e:
                self.quarantine(f"не читается как текст: {e}")
            self._cache = (stamp, text)
        try:
            return json.loads(self._cache[1])
        except json.JSONDecodeError as e:
            self.quarantine(f"не читается как JSON: {e}")

    def write(self, data: Any) -> None:
        text = json.dumps(data, ensure_ascii=False, indent=2)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(self.path)
            stat = self.path.stat()
            self._cache = ((stat.st_mtime_ns, stat.st_size), text)

    def quarantine(self, reason: str) -> None:
        """Убрать испорченный файл в сторону (не удалять!) и сообщить об этом."""
        broken = self.path.with_name(f"{self.path.name}.broken-{datetime.now():%Y-%m-%d_%H-%M-%S}")
        self.path.replace(broken)
        self._cache = None
        log.warning("Файл данных %s %s — отложен в %s", self.path, reason, broken.name)
        raise StorageError(f"{self.path.name} {reason}. Испорченный файл сохранён как {broken.name}")


class JsonDocument(Generic[M]):
    """Один объект в файле: настройки, состояние."""

    def __init__(self, path: Path, model: type[M], default: M | Callable[[], M] | None = None):
        self._file = JsonFile(path)
        self.model = model
        self._default = default

    @property
    def path(self) -> Path:
        return self._file.path

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> M:
        """Объект из файла; файла нет — значение по умолчанию (default или model())."""
        data = self._file.read()
        if data is None:
            if self._default is None:
                return self.model()
            return self._default() if callable(self._default) else self._default.model_copy(deep=True)
        try:
            return self.model.model_validate(data)
        except ValidationError as e:
            self._file.quarantine(f"не подходит под {self.model.__name__}: {e.error_count()} ошиб.")

    def save(self, value: M) -> M:
        self._file.write(value.model_dump(mode="json"))
        return value

    def update(self, change: Callable[[M], M | None]) -> M:
        """Прочитать → изменить → записать. change может вернуть новый объект или поменять переданный."""
        value = self.load()
        result = change(value)
        return self.save(value if result is None else result)


class JsonCollection(Generic[M]):
    """Набор записей с ключом в файле — список объектов, порядок сохраняется."""

    def __init__(self, path: Path, model: type[M], key: str):
        self._file = JsonFile(path)
        self.model = model
        self.key = key
        self._adapter = TypeAdapter(list[model])

    @property
    def path(self) -> Path:
        return self._file.path

    def all(self) -> list[M]:
        data = self._file.read()
        if data is None:
            return []
        try:
            return self._adapter.validate_python(data)
        except ValidationError as e:
            self._file.quarantine(f"не подходит под список {self.model.__name__}: {e.error_count()} ошиб.")

    def get(self, key: Any) -> M | None:
        return next((item for item in self.all() if getattr(item, self.key) == key), None)

    def filter(self, predicate: Callable[[M], bool]) -> list[M]:
        return [item for item in self.all() if predicate(item)]

    def put(self, item: M) -> M:
        """Добавить или заменить по ключу (на том же месте)."""
        self.put_many([item])
        return item

    def put_many(self, items: list[M]) -> None:
        new = {getattr(item, self.key): item for item in items}
        result = []
        for current in self.all():
            key = getattr(current, self.key)
            result.append(new.pop(key) if key in new else current)
        result.extend(new.values())
        self.replace_all(result)

    def delete(self, key: Any) -> bool:
        items = self.all()
        kept = [item for item in items if getattr(item, self.key) != key]
        if len(kept) == len(items):
            return False
        self.replace_all(kept)
        return True

    def replace_all(self, items: list[M]) -> None:
        self._file.write([item.model_dump(mode="json") for item in items])


class DataDir:
    """Папка данных плагина (ctx.data): имена файлов — относительно неё, выйти наружу нельзя."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._opened: dict[tuple[str, str], Any] = {}

    def path(self, name: str | Path) -> Path:
        """Путь внутри папки данных. «../…» и абсолютные пути — StorageError."""
        relative = Path(name)
        root = self.root.resolve()
        target = (root / relative).resolve()
        if relative.is_absolute() or not target.is_relative_to(root) or target == root:
            raise StorageError(f"{name}: файлы плагина — только внутри его папки данных")
        return target

    def collection(self, name: str, model: type[M], key: str) -> JsonCollection[M]:
        """Коллекция в файле name. Повторный вызов с тем же именем — тот же объект (один кэш на файл)."""
        return self._open(("collection", name), lambda: JsonCollection(self.path(name), model, key))

    def document(self, name: str, model: type[M], default: M | Callable[[], M] | None = None) -> JsonDocument[M]:
        return self._open(("document", name), lambda: JsonDocument(self.path(name), model, default))

    def file(self, name: str) -> JsonFile:
        """Сырой JSON-файл (без модели): read() / write()."""
        return self._open(("file", name), lambda: JsonFile(self.path(name)))

    def _open(self, key: tuple[str, str], create: Callable[[], Any]) -> Any:
        if key not in self._opened:
            self._opened[key] = create()
        return self._opened[key]
