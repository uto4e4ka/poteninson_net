import asyncio
from typing import Callable, Awaitable

from nats.aio.subscription import Subscription

from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.discord_models import Command, ExecutedCommand, ExecutedCommandResponse
from potehinsonnet.net_models.system_models import Service


class CommandRegistrator:
    def __init__(self,nats_client:NatsClient,plugin:Service):
        self.plugin_name = plugin.name
        self.nats_client = nats_client
        self.plugin_label = plugin.label
        self.subs:dict[str,Subscription] = {}

    def _create_listener(
            self,
            listener: Callable[
                [ExecutedCommand],
                Awaitable[ExecutedCommandResponse]
            ],
    ):
        async def on_call(body) -> dict:
            body = ExecutedCommand.model_validate(body)
            print("callback")
            result = await listener(body)

            return result.model_dump(mode="json")

        return on_call

    async def register_command(self, commands):
        for command, listener in commands:
            key = f"{command.service}.{command.tag}"

            if key in self.subs:
                raise KeyError("tag must be unique")

            await self.nats_client.publish(
                "discord.command.register",
                command.model_dump(mode="json"),
            )

            on_call = self._create_listener(listener)

            self.subs[key] = await self.nats_client.subscribe(
                f"discord.command.execute.{command.service}.{command.tag}",
                on_call,
            )

        await self.nats_client.publish(
            "discord.command.sync",
            {},
        )

    async def reply(self,entity_id:str,response:ExecutedCommandResponse):
        await self.nats_client.publish(f"discord.command.reply.{entity_id}",response.model_dump(mode="json"))


    async def unregister_command(self,commands:list[tuple[Command, Callable[[ExecutedCommand], Awaitable[ExecutedCommandResponse]]]]):
        for command, listener in commands:
            await self.nats_client.publish("discord.command.remove",command.model_dump(mode='json'))
            key = f"{command.service}.{command.tag}"
            sub = self.subs.pop(key,None)
            if sub:
                await sub.unsubscribe()
        await self.nats_client.publish("discord.command.sync", {})