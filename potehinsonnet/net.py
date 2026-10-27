# src/nats_client/client.py

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

import nats
from nats.aio.client import Client
from nats.aio.msg import Msg
from nats.aio.subscription import Subscription

logger = logging.getLogger(__name__)

# Ключ, которым обработчик сообщает об ошибке в ответе на request
ERROR_KEY = "__error__"


class NatsRequestError(Exception):
    """Обработчик на другой стороне упал при выполнении запроса."""


def _dumps(data: dict | None) -> bytes:
    return json.dumps(
        data,
        default=lambda obj: obj.isoformat(),
    ).encode()


class NatsClient:
    def __init__(self, url: str = "nats://localhost:4222"):
        self.url = url
        self._client: Client = Client()

    async def connect(self) -> None:
        await self._client.connect(self.url)

    async def publish(
            self,
            subject: str,
            data: dict | None,
    ) -> None:
        await self._client.publish(
            subject,
            _dumps(data),
        )

    async def subscribe(
            self,
            subject: str,
            handler: Callable[[dict], Awaitable[dict | None]],
            concurrent: bool = False,
    ) -> Subscription:
        """Подписка: handler получает тело сообщения, его ответ уходит на request.

        NATS отдаёт сообщения одной подписки по очереди. concurrent=True — каждое в своей задаче:
        для запросов, которые не зависят друг от друга (страницы панели), иначе медленный держит остальных.
        Где важен порядок (кадры анимации, поток ответов), оставляйте по умолчанию.
        """
        tasks: set[asyncio.Task] = set()

        async def handle(message: Msg) -> None:
            try:
                data = json.loads(message.data)
                response = await handler(data)
            except Exception as e:
                logger.exception(f"Ошибка обработчика NATS [{subject}]: {e}")
                # Отвечаем ошибкой сразу, чтобы запрашивающий не ждал таймаута
                if message.reply:
                    await message.respond(_dumps({ERROR_KEY: f"{type(e).__name__}: {e}"}))
                return

            if response is not None and message.reply:
                await message.respond(_dumps(response))

        async def callback(message: Msg) -> None:
            if not concurrent:
                await handle(message)
                return
            task = asyncio.create_task(handle(message))
            tasks.add(task)
            task.add_done_callback(tasks.discard)

        return await self._client.subscribe(
            subject,
            cb=callback,
        )

    async def request(
            self,
            subject: str,
            payload: dict,
            timeout: float = 10.0,
    ) -> dict:
        message = await self._client.request(
            subject,
            _dumps(payload),
            timeout=timeout,
        )

        response = json.loads(message.data)
        if isinstance(response, dict) and ERROR_KEY in response:
            raise NatsRequestError(response[ERROR_KEY])
        return response

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
