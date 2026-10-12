import pytest

from potehinsonnet.net_models.discord_models import Channel, ExecutedComponent, ExecutedComponentResponse, Guild, User
from potehinsonnet.setup.button_registrator import ButtonRegistrator, button


class Controls:
    def __init__(self):
        self.clicked = []

    @button("music:pause")
    async def pause(self, component):
        self.clicked.append(component.context)
        return ExecutedComponentResponse(message="paused")

    @button("music:fail")
    async def fail(self, component):
        raise ValueError("нельзя")

    @button("music:silent")
    async def silent(self, component):
        return None


def click(custom_id: str, task_id: str = "T1", context: dict | None = None) -> dict:
    return ExecutedComponent(
        id=custom_id,
        user=User(id=1, name="u"),
        guild=Guild(id=2, name="g"),
        channel=Channel(id=3, name="c"),
        task_id=task_id,
        context=context,
    ).model_dump(mode="json")


@pytest.fixture
async def registrator(client):
    reg = ButtonRegistrator(nats_client=client)
    async with reg:
        yield reg


async def test_click_calls_handler_and_replies(bus, client, registrator):
    controls = Controls()
    await registrator.register_instance(controls)

    await client.publish("discord.component.execute", click("music:pause", context={"k": "v"}))
    await bus.settle()

    assert controls.clicked == [{"k": "v"}]
    assert bus.messages("discord.component.T1.reply")[0]["message"] == "paused"


async def test_handler_error_becomes_ephemeral_reply(bus, client, registrator):
    await registrator.register_instance(Controls())

    await client.publish("discord.component.execute", click("music:fail"))
    await bus.settle()

    reply = bus.messages("discord.component.T1.reply")[0]
    assert reply["message"] == "нельзя"
    assert reply["ephemeral"] is True


async def test_handler_returning_none_publishes_null(bus, client, registrator):
    await registrator.register_instance(Controls())

    await client.publish("discord.component.execute", click("music:silent"))
    await bus.settle()

    assert bus.messages("discord.component.T1.reply") == [None]


async def test_unknown_button_is_ignored(bus, client, registrator):
    # Тему discord.component.execute слушают все плагины — чужие кнопки молча пропускаем
    await registrator.register_instance(Controls())

    await client.publish("discord.component.execute", click("other:button"))
    await bus.settle()

    assert bus.messages("discord.component.T1.reply") == []


async def test_exit_unsubscribes(bus, client):
    reg = ButtonRegistrator(nats_client=client)
    async with reg:
        assert bus.has_subscription("discord.component.execute")
    assert not bus.has_subscription("discord.component.execute")
