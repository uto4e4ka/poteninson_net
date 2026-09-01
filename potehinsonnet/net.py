# src/nats_client/client.py

import json
from collections.abc import Awaitable, Callable

import nats
from nats.aio.client import Client


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
        handler: Callable[[dict], Awaitable[None]],
    ) -> None:

        async def callback(message):
            data = json.loads(message.data)
            await handler(data)

        await self._client.subscribe(
            subject,
            cb=callback,
        )

    async def close(self) -> None:
        await self._client.close()