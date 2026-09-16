import asyncio
from functools import wraps
from typing import Callable, Awaitable
from urllib import response
from warnings import deprecated

from nats.aio.subscription import Subscription

from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.discord_models import Command, ExecutedCommand, ExecutedCommandResponse
from potehinsonnet.net_models.system_models import Service

from types import TracebackType


class CommandRegistrator:
    def __init__(self,nats_client:NatsClient,plugin:Service):
        self.plugin_name = plugin.name
        self.nats_client = nats_client
        self.plugin_label = plugin.label
        self.subs:dict[str,Subscription] = {}
        self._commands: dict[
            str,
            tuple[
                Command,
                Callable[
                    [ExecutedCommand],
                    Awaitable[ExecutedCommandResponse | None],
                ],
            ],
        ] = {}

    @staticmethod
    def command(registrator:CommandRegistrator,command: Command):

        def decorator(func:Callable[[ExecutedCommand], Awaitable[ExecutedCommandResponse]]):
            registrator.add_command(command,func)
            @wraps(func)
            async def wrapper(executed_command: ExecutedCommand) -> ExecutedCommandResponse | None:
                response =  await func(executed_command)
                if response:
                    await registrator.reply(executed_command.entity_id,response)
                return response
            return wrapper

        return decorator


    def _create_listener(
            self,
            listener: Callable[
                [ExecutedCommand],
                Awaitable[None]
            ],
    ):
        async def on_call(body):
            body = ExecutedCommand.model_validate(body)
            print("callback")
            await listener(body)

        return on_call


    async def add_command(self,command:Command,listener:Callable[[ExecutedCommand], Awaitable[ExecutedCommandResponse]]):
        key = f"{command.service}.{command.tag}"
        if key in self._commands:
            raise KeyError("tag must be unique")
        self._commands[key] = (command, listener)


    async def push_commands(self,commands:dict[Command,Callable[[ExecutedCommand], Awaitable[ExecutedCommandResponse]]]):
        for command, listener in commands:
            key = f"{command.service}.{command.tag}"
            if key in self.subs:
                raise KeyError("tag must be unique")
            await self.nats_client.publish(
                "discord.command.register",
                command.model_dump(mode="json"),
            )
            on_call = self._create_listener(listener)
            self.subs[command] = await self.nats_client.subscribe(
                f"discord.command.execute.{command.service}.{command.tag}",
                on_call
            )


    async def sync_commands(self):
        await self.nats_client.publish(
            "discord.command.sync",
            {},
        )

    @deprecated("Используйте push_commands()")
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

    async def flush(self):
        for key,sub in self.subs:
            await sub.unsubscribe()
            self.subs.pop(key)
        self._commands.clear()

    async def __aenter__(self):
        return self

    async def __aexit__(self):
        await self.flush()

