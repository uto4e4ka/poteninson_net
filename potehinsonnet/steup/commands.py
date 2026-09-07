import asyncio
from typing import Callable, Awaitable

from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.discord_models import CommandRegister,Command

class Install:
    def __init__(self,nats_client:NatsClient,plugin_name:str,plugin_label:str):
        self.plugin_name = plugin_name
        self.nats_client = nats_client
        self.plugin_label = plugin_label
        asyncio.create_task(self.install_plugin())

    async def install_plugin(self):
        return

    async def register_command(self,command:Command, listener: Callable[[dict], Awaitable[None]],):
        await self.nats_client.publish("discord.command.register",command.model_dump(mode='json'))
        async def on_call(body):
            await listener(body)
        await self.nats_client.subscribe(f"discord.command.execute.{command.service}.{command.name}",on_call)
