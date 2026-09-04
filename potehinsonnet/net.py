# src/nats_client/client.py

import json
from collections.abc import Awaitable, Callable

import nats
from nats.aio.client import Client
from nats.aio.msg import Msg
from nats.aio.subscription import Subscription


class NatsClient:
    def __init__(self, url: str = "nats://localhost:4222"):
        self.url = url
        self._client: Client = Client()

    async def connect(self) -> None:
        await self._client.connect(self.url)


    async def publish(self, subject: str, data: dict) -> None:
        payload = json.dumps(data,
                             default=lambda obj: obj.isoformat()).encode()

        await self._client.publish(
            subject,
            payload,
        )

    async def subscribe(
            self,
            subject: str,
            handler: Callable[[dict], Awaitable[dict | None]],
    ) -> Subscription:  # 1. Меняем возвращаемый тип с None на Subscription
        async def callback(message: Msg) -> None:
            data = json.loads(message.data)

            response = await handler(data)

            if response is not None and message.reply:
                await message.respond(
                    json.dumps(response).encode()
                )
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
            json.dumps(payload).encode(),
            timeout=timeout,
        )

        return json.loads(message.data)

    async def close(self) -> None:
        await self._client.close()

