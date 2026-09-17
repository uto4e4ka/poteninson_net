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

def command(cmd: Command):
    def decorator(func):
        func.__nats_command__ = cmd
        return func
    return decorator

class CommandRegistrator:
    def __init__(self, nats_client: NatsClient, plugin: Service):
        self.nats_client = nats_client
        self.plugin = plugin
        self.subs: dict[str, Subscription] = {}

    async def register_instance_commands(self, instance: object):
        """Сканирует объект (плагин) и подписывает все помеченные @command методы."""
        for attr_name in dir(instance):
            method = getattr(instance, attr_name)

            # Проверяем, есть ли у метода метка от декоратора @command
            if hasattr(method, "__nats_command__"):
                cmd: Command = getattr(method, "__nats_command__")
                if not cmd.service:
                    cmd.service = self.plugin.name
                await self._subscribe_method(cmd, method)

        # Отправляем событие синхронизации в NATS
        await self.nats_client.publish("discord.command.sync", {})

    async def _subscribe_method(
            self,
            cmd: Command,
            method: Callable[[ExecutedCommand], Awaitable[ExecutedCommandResponse | None]]
    ):
        key = f"{cmd.service}.{cmd.tag}"
        if key in self.subs:
            raise KeyError(f"Command tag '{key}' must be unique")

        # Объявляем событие регистрации
        await self.nats_client.publish(
            "discord.command.register",
            cmd.model_dump(mode="json"),
        )

        async def on_call(msg):
            executed_cmd = ExecutedCommand.model_validate_json(msg)

            response = await method(executed_cmd)

            if response:
                await self.nats_client.publish(
                    f"discord.command.reply.{executed_cmd.entity_id}",
                    response.model_dump(mode="json"),
                )

        topic = f"discord.command.execute.{cmd.service}.{cmd.tag}"
        self.subs[key] = await self.nats_client.subscribe(topic, on_call)

    async def close(self):
        """Отписываемся при остановке контейнера."""
        for sub in self.subs.values():
            await sub.unsubscribe()
        self.subs.clear()


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

