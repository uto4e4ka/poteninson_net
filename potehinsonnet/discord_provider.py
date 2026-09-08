from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.discord_models import NatsMessage

class DiscordProvider:
    def __init__(self,nats_client:NatsClient):
        self.nats_client = nats_client

    async def send_message(self, message: NatsMessage):
        await self.nats_client.publish("discord.message.send", message.model_dump(mode="json"))