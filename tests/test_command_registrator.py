import pytest

from potehinsonnet.net_models.discord_models import Command, ExecutedCommandResponse
from potehinsonnet.setup.command_registrator import CommandRegistrator, command
from tests.conftest import make_executed


class Plugin:
    def __init__(self):
        self.calls = []

    @command(Command(name="ok", description="d", tag="ok"))
    async def ok(self, cmd):
        self.calls.append(cmd)
        return ExecutedCommandResponse(message="done", is_final=True)

    @command(Command(name="fail", description="d", tag="fail"))
    async def fail(self, cmd):
        raise RuntimeError("oops")

    @command(Command(name="silent", description="d", tag="silent"))
    async def silent(self, cmd):
        return None

    async def not_a_command(self, cmd):
        raise AssertionError("не должна регистрироваться")


@pytest.fixture
def registrator(client, plugin):
    return CommandRegistrator(nats_client=client, plugin=plugin)


async def test_register_instance_announces_commands_and_syncs(bus, registrator):
    await registrator.register_instance_commands(Plugin())

    registered = bus.messages("discord.command.register")
    assert sorted(c["tag"] for c in registered) == ["fail", "ok", "silent"]
    # service подставляется из имени плагина
    assert {c["service"] for c in registered} == {"test_plugin"}
    assert bus.messages("discord.command.sync") == [{}]
    assert sorted(registrator.subs) == ["test_plugin.fail", "test_plugin.ok", "test_plugin.silent"]


async def test_executed_command_replies_to_entity(bus, client, registrator):
    plugin = Plugin()
    await registrator.register_instance_commands(plugin)

    await client.publish("discord.command.execute.test_plugin.ok", make_executed("ok").model_dump(mode="json"))
    await bus.settle()

    assert plugin.calls[0].tag == "ok"
    reply = bus.messages("discord.command.reply.E1")
    assert reply[0]["message"] == "done"
    assert reply[0]["is_final"] is True


async def test_failing_command_sends_final_error(bus, client, registrator):
    await registrator.register_instance_commands(Plugin())

    await client.publish("discord.command.execute.test_plugin.fail", make_executed("fail").model_dump(mode="json"))
    await bus.settle()

    reply = bus.messages("discord.command.reply.E1")
    assert reply == [ExecutedCommandResponse(message="oops", is_final=True).model_dump(mode="json")]


async def test_command_returning_none_sends_nothing(bus, client, registrator):
    await registrator.register_instance_commands(Plugin())

    await client.publish("discord.command.execute.test_plugin.silent", make_executed("silent").model_dump(mode="json"))
    await bus.settle()

    assert bus.messages("discord.command.reply.>") == []


async def test_reregistering_replaces_subscription(bus, registrator):
    await registrator.register_instance_commands(Plugin())
    await registrator.register_instance_commands(Plugin())

    assert len([s for s in bus.subscriptions if s.subject == "discord.command.execute.test_plugin.ok"]) == 1


async def test_push_commands_and_unregister(bus, client, registrator):
    async def listener(cmd):
        return ExecutedCommandResponse(message="pushed", is_final=True)

    cmd = Command(name="p", description="d", service="test_plugin", tag="p")
    await registrator.push_commands([(cmd, listener)])

    await client.publish("discord.command.execute.test_plugin.p", make_executed("p").model_dump(mode="json"))
    await bus.settle()
    assert bus.messages("discord.command.reply.E1")[0]["message"] == "pushed"

    with pytest.raises(KeyError):
        await registrator.push_commands([(cmd, listener)])

    await registrator.unregister_command([(cmd, listener)])
    assert bus.messages("discord.command.remove")[0]["tag"] == "p"
    assert not bus.has_subscription("discord.command.execute.test_plugin.p")


async def test_deprecated_register_command_still_works(bus, registrator):
    async def listener(cmd):
        return None

    with pytest.warns(DeprecationWarning):
        await registrator.register_command([(Command(name="d", description="d", service="s", tag="d"), listener)])

    assert bus.has_subscription("discord.command.execute.s.d")


async def test_add_command_rejects_duplicates(registrator):
    async def listener(cmd):
        return None

    cmd = Command(name="a", description="d", service="s", tag="a")
    await registrator.add_command(cmd, listener)

    with pytest.raises(KeyError):
        await registrator.add_command(cmd, listener)


async def test_reply_wraps_plain_text(bus, registrator):
    await registrator.reply("E9", "в процессе")
    await registrator.reply("E9", ExecutedCommandResponse(message="готово", is_final=True))

    messages = bus.messages("discord.command.reply.E9")
    assert [m["message"] for m in messages] == ["в процессе", "готово"]
    assert [m["is_final"] for m in messages] == [False, True]


async def test_context_manager_flushes_everything(bus, registrator):
    async def listener(cmd):
        return None

    async with registrator as r:
        await r.register_instance_commands(Plugin())
        await r.add_command(Command(name="a", description="d", service="s", tag="a"), listener)

    assert registrator.subs == {}
    assert registrator._commands == {}
    assert bus.subscriptions == []


async def test_close_unsubscribes(bus, registrator):
    await registrator.register_instance_commands(Plugin())

    await registrator.close()

    assert bus.subscriptions == []
