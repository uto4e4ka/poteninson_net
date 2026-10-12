import importlib
from contextlib import asynccontextmanager

import pytest
from dependency_injector import providers

from potehinsonnet.containers.nats_container import NatsContainer
from potehinsonnet.discord_provider import DiscordProvider
from potehinsonnet.monitoring.health import Health
from potehinsonnet.setup.button_registrator import ButtonRegistrator
from potehinsonnet.setup.command_registrator import CommandRegistrator


def make_container(bus) -> NatsContainer:
    container = NatsContainer()
    container.config.plugin.from_dict({
        "type": "plugin", "name": "demo", "label": "Demo", "description": "",
        "author": "me", "version": "1.0", "icon": "", "site": "",
    })

    @asynccontextmanager
    async def fake_nats(url):
        client = bus.client()
        await client.connect()
        yield client
        await client.close()

    container.nats.override(providers.Resource(fake_nats, url=container.config.nats.url))
    return container


async def test_container_wires_plugin_services(bus):
    container = make_container(bus)
    bot = bus.client()

    async def registration(data):
        return {"type": "bot", "name": "1", "label": "Bot", "author": "", "version": "1"}

    await bot.subscribe("system.info.registration.request", registration)

    await container.init_resources()
    try:
        assert container.plugin().name == "demo"
        assert isinstance(await container.health(), Health)
        assert isinstance(await container.command_registrator(), CommandRegistrator)
        assert isinstance(await container.button_registrator(), ButtonRegistrator)
        provider = await container.discord_provider()
        assert isinstance(provider, DiscordProvider)
        # один NATS-клиент на весь плагин
        assert provider.nats_client is await container.nats()
        assert (await container.health()).has_registration
        assert bus.messages("system.info.request")[-1] == {
            "type": "plugin", "name": "demo", "status": "ENABLED✅", "time": bus.messages("system.info.request")[-1]["time"],
        }
        assert bus.has_subscription("discord.component.execute")
    finally:
        await container.shutdown_resources()

    assert bus.messages("system.info.request")[-1]["status"] == "DISABLED❌"
    assert not bus.has_subscription("discord.component.execute")
    assert not bus.has_subscription("system.info.response")


def test_container_is_deprecated():
    import potehinsonnet.containers.nats_container as module

    with pytest.warns(DeprecationWarning, match="potehinsonnet.Plugin"):
        importlib.reload(module)


def test_default_nats_url():
    assert NatsContainer().config.nats.url() == "nats://localhost:4222"
