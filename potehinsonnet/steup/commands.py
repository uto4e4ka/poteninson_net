import asyncio

from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.discord_models import CommandRegister

class Install:
    def __init__(self,nats_client:NatsClient,plugin_name:str,plugin_label:str):
        self.plugin_name = plugin_name
        self.nats_client = nats_client
        self.plugin_label = plugin_label
        asyncio.create_task(self.install_plugin())

    async def install_plugin(self):
        return

    async def register_commands(self,commands:CommandRegister):
        await self.nats_client.publish("discord.command.register",commands.model_dump(mode='json'))

