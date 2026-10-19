"""Большие файлы через NATS Object Store (JetStream): zip с плагином, звуки, архивы — любого размера.

Обычное сообщение NATS — до 1 МБ, поэтому большой файл не передают в теле запроса, а кладут
в хранилище и передают ссылку (FileRef). Хранилище само режет файл на куски и собирает обратно.

    ref = await files.put(open("plugin.zip", "rb"), "plugin.zip")   # панель
    await files.save(ref, Path("/tmp/plugin.zip"))                  # плагин или бот

Загрузки из панели лежат в ведре panel-uploads и сами удаляются через час: кто забрал — тот забрал.
На сервере NATS должен быть запущен с JetStream (`nats-server -js`).
"""
import io
import uuid
from pathlib import Path
from typing import BinaryIO

from nats.js.api import ObjectStoreConfig, StorageType
from nats.js.errors import BucketNotFoundError, NotFoundError, ObjectNotFoundError

from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.panel_ui import FileRef

UPLOADS_BUCKET = "panel-uploads"
UPLOADS_TTL = 3600.0   # секунд: забытые загрузки не копятся на диске


class FileStore:

    def __init__(self, nats: NatsClient, bucket: str = UPLOADS_BUCKET, ttl: float | None = UPLOADS_TTL):
        self.nats = nats
        self.bucket = bucket
        self.ttl = ttl
        self._store = None

    async def _get_store(self, bucket: str | None = None):
        bucket = bucket or self.bucket
        if bucket == self.bucket and self._store is not None:
            return self._store
        js = self.nats._client.jetstream()
        try:
            store = await js.object_store(bucket)
        except (BucketNotFoundError, NotFoundError):
            if bucket != self.bucket:
                raise FileNotFoundError(f"Нет хранилища {bucket}")
            config = ObjectStoreConfig(bucket=bucket, ttl=self.ttl, storage=StorageType.FILE)
            store = await js.create_object_store(bucket, config=config)
        if bucket == self.bucket:
            self._store = store
        return store

    async def put(self, source: bytes | BinaryIO, filename: str) -> FileRef:
        """Положить файл (байты или открытый файл — читается кусками, целиком в память не грузится)."""
        store = await self._get_store()
        data = io.BytesIO(source) if isinstance(source, bytes) else source
        name = uuid.uuid4().hex
        info = await store.put(name, data)
        return FileRef(bucket=self.bucket, name=name, filename=Path(filename).name or name, size=info.size)

    async def read(self, ref: FileRef) -> bytes:
        """Весь файл в память — для небольших. Большие лучше save()."""
        store = await self._get_store(ref.bucket)
        try:
            return (await store.get(ref.name)).data
        except ObjectNotFoundError:
            raise FileNotFoundError(f"Файл {ref.filename} не найден — загрузка устарела, загрузите ещё раз")

    async def save(self, ref: FileRef, path: Path) -> Path:
        """Сохранить файл на диск потоком."""
        store = await self._get_store(ref.bucket)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("wb") as out:
                await store.get(ref.name, writeinto=out)
        except ObjectNotFoundError:
            path.unlink(missing_ok=True)
            raise FileNotFoundError(f"Файл {ref.filename} не найден — загрузка устарела, загрузите ещё раз")
        return path

    async def delete(self, ref: FileRef) -> None:
        store = await self._get_store(ref.bucket)
        try:
            await store.delete(ref.name)
        except ObjectNotFoundError:
            pass
