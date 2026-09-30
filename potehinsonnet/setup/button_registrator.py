from typing import Awaitable, Callable

from nats.aio.subscription import Subscription

from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.discord_models import ExecutedComponentResponse, ExecutedComponent, ExecutedCommand

from types import TracebackType


def button(custom_id: str):
    def decorator(func:Callable[[ExecutedComponent], Awaitable[ExecutedComponentResponse|None]]):
        func.__custom_id__ = custom_id
        return func
    return decorator

class ButtonRegistrator:
    def __init__(self, nats_client: NatsClient):
        self.nats_client = nats_client
        self.sub:Subscription|None =  None
        self.components:dict[str,Callable[[ExecutedComponent], Awaitable[ExecutedComponentResponse|None]]] = {}


    async def register_instance(self,instance:object):
        for attr_name in dir(instance):
            method = getattr(instance, attr_name)

            # Проверяем, есть ли у метода метка от декоратора @command
            if hasattr(method, "__custom_id__"):
                custom_id: str = getattr(method, "__custom_id__")
                self.components[custom_id] = method

    async def on_click(self,body:dict):
        executed = ExecutedComponent.model_validate(body)
        method = self.components.get(executed.id)
        if method is None:
            return
        result = await method(executed)
        if result:
            await self.nats_client.publish(
                f"discord.component.{executed.task_id}.reply",
                result.model_dump(mode="json"),
            )

    async def subscribe(self):
        self.sub = await self.nats_client.subscribe("discord.component.execute",self.on_click)

    async def unsubscribe(self):
        if self.sub:
            await self.sub.unsubscribe()

    async def __aenter__(self):
        await self.subscribe()

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None):
        await self.unsubscribe()

