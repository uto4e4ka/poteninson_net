"""In-memory замена NATS для тестов бота и плагинов.

    bus = FakeNats()
    client = bus.client()          # обычный NatsClient, но без сервера
    await client.subscribe("a.*", handler)
    await client.publish("a.b", {"x": 1})
    await bus.settle()             # дождаться, пока все обработчики отработают

Поведение повторяет nats-py:
- сообщения доставляются асинхронно, поэтому гонка "публикация до подписки"
  воспроизводится так же, как в проде;
- сообщения одной подписки обрабатываются строго по очереди;
- unsubscribe() из обработчика своей же подписки отменяет этот обработчик,
  код после отписки не выполнится.

Объектное хранилище JetStream (для FileStore) тоже есть: файлы лежат в памяти, bus.objects[ведро][имя].
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Awaitable, Callable

from nats.js.errors import BucketNotFoundError, ObjectNotFoundError

from potehinsonnet.net import NatsClient


def subject_matches(pattern: str, subject: str) -> bool:
    """Сопоставление темы с шаблоном NATS (`*` — один токен, `>` — хвост)."""
    p_tokens = pattern.split(".")
    s_tokens = subject.split(".")
    for i, p in enumerate(p_tokens):
        if p == ">":
            return len(s_tokens) > i
        if i >= len(s_tokens):
            return False
        if p != "*" and p != s_tokens[i]:
            return False
    return len(p_tokens) == len(s_tokens)


@dataclass
class FakeMsg:
    subject: str
    data: bytes
    reply: str
    _bus: "FakeNats"

    async def respond(self, data: bytes) -> None:
        if self.reply:
            await self._bus.publish(self.reply, data)


@dataclass
class FakeSubscription:
    subject: str
    cb: Callable[[FakeMsg], Awaitable[None]]
    _bus: "FakeNats"
    closed: bool = False
    busy: bool = False
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    task: asyncio.Task | None = None

    def start(self) -> None:
        self.task = asyncio.create_task(self._process())

    async def _process(self) -> None:
        while True:
            msg = await self.queue.get()
            self.busy = True
            try:
                await self.cb(msg)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                # nats-py передаёт такие ошибки в error_cb и продолжает работу
                self._bus.errors.append(e)
            finally:
                self.busy = False

    async def unsubscribe(self) -> None:
        if self.closed:
            raise RuntimeError(f"Подписка {self.subject} уже закрыта")
        self.closed = True
        self._bus.subscriptions.remove(self)
        if self.task and not self.task.done():
            self.task.cancel()
        # Как в nats-py: если отписка вызвана из своего же обработчика, здесь он и прервётся
        await asyncio.sleep(0)

    @property
    def idle(self) -> bool:
        return self.closed or (self.queue.empty() and not self.busy)


class FakeObjectStore:
    """Как nats.js.object_store.ObjectStore: put / get / delete, файлы — в памяти."""

    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects

    async def put(self, name: str, data, meta=None):
        content = data if isinstance(data, (bytes, str)) else data.read()
        self.objects[name] = content.encode() if isinstance(content, str) else content
        return SimpleNamespace(name=name, size=len(self.objects[name]))

    async def get(self, name: str, writeinto=None, show_deleted=False):
        if name not in self.objects:
            raise ObjectNotFoundError()
        if writeinto is not None:
            writeinto.write(self.objects[name])
            return SimpleNamespace(data=None)
        return SimpleNamespace(data=self.objects[name])

    async def delete(self, name: str):
        if self.objects.pop(name, None) is None:
            raise ObjectNotFoundError()
        return SimpleNamespace()


class FakeJetStream:
    def __init__(self, bus: "FakeNats"):
        self.bus = bus

    async def object_store(self, bucket: str) -> FakeObjectStore:
        if bucket not in self.bus.objects:
            raise BucketNotFoundError()
        return FakeObjectStore(self.bus.objects[bucket])

    async def create_object_store(self, bucket: str = None, config=None, **params) -> FakeObjectStore:
        self.bus.objects.setdefault(bucket, {})
        return FakeObjectStore(self.bus.objects[bucket])


@dataclass
class FakeNats:
    """Подменяет `nats.aio.client.Client` внутри `NatsClient`."""

    subscriptions: list[FakeSubscription] = field(default_factory=list)
    published: list[tuple[str, Any]] = field(default_factory=list)
    errors: list[Exception] = field(default_factory=list)
    objects: dict[str, dict[str, bytes]] = field(default_factory=dict)   # хранилище файлов: ведро → имя → байты

    def jetstream(self) -> FakeJetStream:
        return FakeJetStream(self)

    def client(self) -> NatsClient:
        nats_client = NatsClient()
        nats_client._client = self
        return nats_client

    async def connect(self, *args, **kwargs) -> None:
        pass

    async def close(self) -> None:
        for sub in list(self.subscriptions):
            if not sub.closed:   # кто-то мог отписаться, пока мы закрывались
                await sub.unsubscribe()

    async def subscribe(self, subject: str, cb) -> FakeSubscription:
        sub = FakeSubscription(subject=subject, cb=cb, _bus=self)
        sub.start()
        self.subscriptions.append(sub)
        return sub

    async def publish(self, subject: str, payload: bytes, reply: str = "") -> None:
        if not subject.startswith("_INBOX."):
            self.published.append((subject, json.loads(payload)))
        for sub in list(self.subscriptions):
            if subject_matches(sub.subject, subject):
                sub.queue.put_nowait(FakeMsg(subject=subject, data=payload, reply=reply, _bus=self))

    async def request(self, subject: str, payload: bytes, timeout: float = 10.0) -> FakeMsg:
        inbox = f"_INBOX.{uuid.uuid4().hex}"
        future: asyncio.Future = asyncio.get_running_loop().create_future()

        async def on_reply(msg: FakeMsg) -> None:
            if not future.done():
                future.set_result(msg)

        sub = await self.subscribe(inbox, on_reply)
        try:
            await self.publish(subject, payload, reply=inbox)
            return await asyncio.wait_for(future, timeout)
        finally:
            await sub.unsubscribe()

    async def settle(self, timeout: float = 5.0) -> None:
        """Ждёт, пока доставятся все сообщения, включая порождённые обработчиками.

        Обработчик, который сам ждёт чего-то вечно, считается занятым — тогда упадёт по таймауту.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        idle_rounds = 0
        while idle_rounds < 3:
            await asyncio.sleep(0)
            if all(sub.idle for sub in self.subscriptions):
                idle_rounds += 1
            else:
                idle_rounds = 0
                if loop.time() > deadline:
                    raise TimeoutError("Обработчики NATS не завершились")
                await asyncio.sleep(0.001)

    def messages(self, subject: str) -> list[Any]:
        """Тела всех сообщений, опубликованных в тему (шаблоны NATS работают)."""
        return [data for subj, data in self.published if subject_matches(subject, subj)]

    def has_subscription(self, subject: str) -> bool:
        return any(sub.subject == subject for sub in self.subscriptions)
