from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.discord_models import NatsMessage, DiscordMessageResponse, DiscordMessageRemove, \
    DiscordMessageEdit, DirectMessage


class DiscordProvider:
    def __init__(self,nats_client:NatsClient):
        self.nats_client = nats_client

    async def send_message(self, message: NatsMessage)->DiscordMessageResponse:
       response = await self.nats_client.request("discord.message.send", message.model_dump(mode="json"))
       return DiscordMessageResponse.model_validate(response)

    async def send_direct_message(self, user_id: int, message: NatsMessage) -> DiscordMessageResponse:
        """Написать пользователю в личку. channel_id ответа — канал лички: по нему сообщение можно
        потом изменить (update_message). Закрытая личка — NatsRequestError."""
        response = await self.nats_client.request(
            "discord.message.send_dm", DirectMessage(user_id=user_id, message=message).model_dump(mode="json"),
        )
        return DiscordMessageResponse.model_validate(response)

    async def remove_message(self,channel_id:int,message_id:int):
        await self.nats_client.publish("discord.message.remove", DiscordMessageRemove(
            channel_id=channel_id,
            message_id=message_id
        ).model_dump(mode="json"))

    async def update_message(self, message: DiscordMessageEdit) -> DiscordMessageResponse:
        response = await self.nats_client.request("discord.message.edit", message.model_dump(mode="json"))
        return DiscordMessageResponse.model_validate(response)