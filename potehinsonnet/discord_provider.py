from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.discord_models import NatsMessage, DiscordMessageResponse, DiscordMessageRemove


class DiscordProvider:
    def __init__(self,nats_client:NatsClient):
        self.nats_client = nats_client

    async def send_message(self, message: NatsMessage)->DiscordMessageResponse:
       response = await self.nats_client.request("discord.message.send", message.model_dump(mode="json"))
       return DiscordMessageResponse.model_validate(response)
    async def remove_message(self,channel_id:int,message_id:int):
        await self.nats_client.request("discord.message.remove", DiscordMessageRemove(
            channel_id=channel_id,
            message_id=message_id
        ).model_dump(mode="json"))