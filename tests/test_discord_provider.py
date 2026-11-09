import pytest

from potehinsonnet.discord_provider import DiscordProvider
from potehinsonnet.net import NatsRequestError
from potehinsonnet.net_models.discord_models import DiscordMessageEdit, ExecutedComponent, NatsMessage


async def test_send_message_returns_ids(bus, client):
    async def bot_send(data):
        assert data["text"] == "hi"
        return {"channel_id": data["channel_id"], "message_id": 555}

    await client.subscribe("discord.message.send", bot_send)

    response = await DiscordProvider(client).send_message(NatsMessage(service="s", text="hi", channel_id=7))

    assert (response.channel_id, response.message_id) == (7, 555)


async def test_update_message(client):
    async def bot_edit(data):
        return {"channel_id": data["message"]["channel_id"], "message_id": data["message_id"]}

    await client.subscribe("discord.message.edit", bot_edit)

    response = await DiscordProvider(client).update_message(
        DiscordMessageEdit(message_id=9, message=NatsMessage(service="s", text="new", channel_id=7))
    )

    assert response.message_id == 9


async def test_remove_message_publishes(bus, client):
    await DiscordProvider(client).remove_message(channel_id=1, message_id=2)

    assert bus.messages("discord.message.remove") == [{"channel_id": 1, "message_id": 2}]


async def test_send_direct_message(client):
    async def bot_dm(data):
        assert data["user_id"] == 42 and data["message"]["text"] == "привет"
        return {"channel_id": 900, "message_id": 1}

    await client.subscribe("discord.message.send_dm", bot_dm)

    response = await DiscordProvider(client).send_direct_message(42, NatsMessage(service="s", text="привет"))

    assert (response.channel_id, response.message_id) == (900, 1)


async def test_send_direct_message_closed_dm_raises(client):
    async def bot_dm(data):
        raise PermissionError("личка закрыта")

    await client.subscribe("discord.message.send_dm", bot_dm)

    with pytest.raises(NatsRequestError, match="личка закрыта"):
        await DiscordProvider(client).send_direct_message(42, NatsMessage(service="s", text="x"))


def test_component_click_in_dm_has_no_guild():
    executed = ExecutedComponent.model_validate(
        {"id": "x", "user": {"id": 1, "name": "u"}, "channel": {"id": 2, "name": "dm"}, "task_id": "t"}
    )
    assert executed.guild is None
