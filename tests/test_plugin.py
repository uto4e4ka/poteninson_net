import asyncio
from contextlib import asynccontextmanager

import pytest

from potehinsonnet import Plugin
from potehinsonnet.net_models.discord_models import (
    Command,
    ExecutedCommandResponse,
    ExecutedComponentResponse,
)
from potehinsonnet.net_models.system_models import Service
from potehinsonnet.setup.button_registrator import button
from potehinsonnet.setup.command_registrator import command
from tests.conftest import make_executed
from tests.test_button_registrator import click

SERVICE = Service(name="demo", label="Demo", author="me", version="1.0")


@pytest.fixture
async def bot(bus):
    """Бот: отвечает на регистрацию плагинов."""
    client = bus.client()

    async def registration(data):
        return {"type": "bot", "name": "999", "label": "Potehinson", "author": "", "version": "1"}

    await client.subscribe("system.info.registration.request", registration)
    return client


@pytest.fixture
def plugin(client):
    return Plugin(SERVICE, nats=client)


class MusicCommands:
    def __init__(self):
        self.played = []

    @command(Command(name="play", description="d", tag="play"))
    async def play(self, cmd):
        self.played.append(cmd.tag)
        return ExecutedCommandResponse(message="играю", is_final=True)

    @button("music:skip")
    async def skip(self, click):
        return ExecutedComponentResponse(message="пропущено")


async def test_function_command_and_button(plugin, bus, bot):
    @plugin.command(Command(name="beer", description="Цена пива", tag="beer"))
    async def beer(cmd):
        return ExecutedCommandResponse(message="100 ₽", is_final=True)

    @plugin.button("beer:refresh")
    async def refresh(click):
        return ExecutedComponentResponse(message="обновлено")

    async with plugin:
        assert [c["tag"] for c in bus.messages("discord.command.register")] == ["beer"]
        assert bus.messages("discord.command.register")[0]["service"] == "demo"

        await bot.publish("discord.command.execute.demo.beer", make_executed("beer", service="demo").model_dump(mode="json"))
        await bot.publish("discord.component.execute", click("beer:refresh"))
        await bus.settle()

    assert bus.messages("discord.command.reply.E1")[0]["message"] == "100 ₽"
    assert bus.messages("discord.component.T1.reply")[0]["message"] == "обновлено"


async def test_registered_objects(plugin, bus, bot):
    music = MusicCommands()
    plugin.register(music)

    async with plugin:
        await bot.publish("discord.command.execute.demo.play", make_executed("play", service="demo").model_dump(mode="json"))
        await bot.publish("discord.component.execute", click("music:skip"))
        await bus.settle()

    assert music.played == ["play"]
    assert bus.messages("discord.component.T1.reply")[0]["message"] == "пропущено"


async def test_commands_synced_once(plugin, bus, bot):
    plugin.register(MusicCommands())

    @plugin.command(Command(name="beer", description="d", tag="beer"))
    async def beer(cmd):
        return None

    async with plugin:
        pass

    assert sorted(c["tag"] for c in bus.messages("discord.command.register")) == ["beer", "play"]
    assert len(bus.messages("discord.command.sync")) == 1


async def test_commands_reinstalled_when_bot_restarts(plugin, bus, bot):
    plugin.register(MusicCommands())

    async with plugin:
        await bot.publish("system.info.registration.init", {})
        await bus.settle()

        assert len(bus.messages("discord.command.register")) == 2
        # команда по-прежнему работает (подписка пересоздана, а не задублирована)
        assert len([s for s in bus.subscriptions if s.subject == "discord.command.execute.demo.play"]) == 1


async def test_commands_wait_for_bot(plugin, bus, client, monkeypatch):
    # Бот ещё не запущен: плагин стартует, а команды отправит, когда бот попросит
    async def no_bot(subject, payload, timeout=10.0):
        raise TimeoutError()

    plugin.register(MusicCommands())
    monkeypatch.setattr(client, "request", no_bot)

    async with plugin:
        assert bus.messages("discord.command.register") == []
        monkeypatch.undo()
        bot = bus.client()

        async def registration(data):
            return {"type": "bot", "name": "999", "label": "Bot", "author": "", "version": "1"}

        await bot.subscribe("system.info.registration.request", registration)
        await bot.publish("system.info.registration.init", {})
        await bus.settle()

        assert [c["tag"] for c in bus.messages("discord.command.register")] == ["play"]


async def test_lifespans_run_in_order_and_close_in_reverse(plugin, bot):
    events = []

    def lifespan(name):
        @asynccontextmanager
        async def cm():
            events.append(f"start {name}")
            yield
            events.append(f"stop {name}")
        return cm()

    plugin.add_lifespan(lifespan("a"))
    plugin.add_lifespan(lifespan("b"))

    async with plugin:
        events.append("running")

    assert events == ["start a", "start b", "running", "stop b", "stop a"]


async def test_stop_reports_disabled_and_cleans_subscriptions(plugin, bus, bot):
    plugin.register(MusicCommands())

    async with plugin:
        pass

    assert bus.messages("system.info.request")[-1]["status"] == "DISABLED❌"
    assert [s.subject for s in bus.subscriptions] == ["system.info.registration.request"]   # остался только бот


async def test_failed_start_cleans_up(plugin, bus, bot):
    @asynccontextmanager
    async def broken():
        raise RuntimeError("не смог стартовать")
        yield

    @asynccontextmanager
    async def ok():
        yield

    plugin.add_lifespan(ok())
    plugin.add_lifespan(broken())

    with pytest.raises(RuntimeError, match="не смог"):
        await plugin.start()

    assert plugin._stack is None


async def test_registration_after_start_is_rejected(plugin, bot):
    async with plugin:
        with pytest.raises(RuntimeError):
            plugin.register(MusicCommands())
        with pytest.raises(RuntimeError):
            plugin.command(Command(name="x", description="d", tag="x"))(lambda cmd: None)


async def test_owned_nats_is_connected_and_closed(bus, monkeypatch):
    events = []
    client = bus.client()

    async def connect():
        events.append("connect")

    async def close():
        events.append("close")

    monkeypatch.setattr(client, "connect", connect)
    monkeypatch.setattr(client, "close", close)
    monkeypatch.setattr("potehinsonnet.plugin.NatsClient", lambda url: client)

    async def no_bot(subject, payload, timeout=10.0):
        raise TimeoutError()

    monkeypatch.setattr(client, "request", no_bot)

    async with Plugin(SERVICE, nats_url="nats://example:4222"):
        events.append("running")

    assert events == ["connect", "running", "close"]


async def test_serve_stops_on_cancel(plugin, bus, bot):
    task = asyncio.create_task(plugin.serve())
    await asyncio.sleep(0.01)
    assert bus.has_subscription("discord.component.execute")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert not bus.has_subscription("discord.component.execute")
