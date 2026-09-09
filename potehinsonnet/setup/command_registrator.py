import asyncio
from typing import Callable, Awaitable

from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.discord_models import Command, ExecutedCommand, ExecutedCommandResponse
from potehinsonnet.net_models.system_models import Service


class CommandRegistrator:
    def __init__(self,nats_client:NatsClient,plugin:Service):
        self.plugin_name = plugin.name
        self.nats_client = nats_client
        self.plugin_label = plugin.label
        self.subs = {}

    async def register_command(self,command:Command, listener: Callable[[ExecutedCommand], Awaitable[ExecutedCommandResponse]]):
        if f"{command.service}.{command.tag}" in self.subs.keys():
            raise KeyError("tag must be unique")
        await self.nats_client.publish("discord.command.register",command.model_dump(mode='json'))
        async def on_call(body)->dict:
            body = ExecutedCommand.model_validate(body)
            result = await listener(body)
            return result.model_dump(mode='json')

        self.subs[f"{command.service}.{command.tag}"] = await self.nats_client.subscribe(
            f"discord.command.execute.{command.service}.{command.tag}",
            on_call)


    async def unregister_command(self,command:Command):
        await self.nats_client.publish("discord.command.remove",command.model_dump(mode='json'))
        key = f"{command.service}.{command.tag}"
        sub = self.subs.pop(key,None)
        if sub:
            sub.unsubscribe()