import pytest

from potehinsonnet.monitoring.health import Health
from potehinsonnet.net_models.system_models import ServiceRegistrationResponse


@pytest.fixture
async def main_bot(client):
    """Имитирует бота: отвечает на регистрацию плагинов."""
    bot_service = ServiceRegistrationResponse(type="bot", name="123", label="Potehinson", author="", version="0.0.1")

    async def on_registration(data):
        return bot_service.model_dump(mode="json")

    await client.subscribe("system.info.registration.request", on_registration)
    return bot_service


async def test_start_registers_and_reports_enabled(bus, client, plugin, main_bot):
    health = Health(client=client, plugin=plugin)

    await health.start()

    assert health.has_registration
    assert health.main_service.name == "123"
    statuses = bus.messages("system.info.request")
    assert statuses[-1]["name"] == "test_plugin"
    assert statuses[-1]["status"] == "ENABLED✅"


async def test_start_without_bot_does_not_crash(bus, client, plugin, monkeypatch):
    # Бот ещё не запущен — никто не отвечает на регистрацию
    async def fast_request(subject, payload, timeout=10.0):
        raise TimeoutError()

    monkeypatch.setattr(client, "request", fast_request)
    health = Health(client=client, plugin=plugin)

    await health.start()

    assert not health.has_registration
    assert bus.messages("system.info.request")[-1]["status"] == "ENABLED✅"


async def test_listeners_receive_bot_service(client, plugin, main_bot):
    received = []

    async def listener(service):
        received.append(service.name)

    health = Health(client=client, plugin=plugin)
    await health.add_listener(listener)   # до регистрации
    await health.start()

    async def late_listener(service):
        received.append(("late", service.name))

    await health.add_listener(late_listener)   # после регистрации — вызывается сразу

    assert received == ["123", ("late", "123")]


async def test_reregisters_when_bot_restarts(bus, client, plugin, main_bot):
    received = []

    async def listener(service):
        received.append(service.name)

    health = Health(client=client, plugin=plugin)
    await health.add_listener(listener)
    await health.start()

    await client.publish("system.info.registration.init", {})
    await bus.settle()

    assert received == ["123", "123"]


async def test_answers_health_poll(bus, client, plugin, main_bot):
    health = Health(client=client, plugin=plugin)
    await health.start()
    before = len(bus.messages("system.info.request"))

    await client.publish("system.info.response", {})
    await bus.settle()

    assert len(bus.messages("system.info.request")) == before + 1


async def test_stop_reports_disabled_and_unsubscribes(bus, client, plugin, main_bot):
    async with Health(client=client, plugin=plugin):
        pass

    assert bus.messages("system.info.request")[-1]["status"] == "DISABLED❌"
    assert not bus.has_subscription("system.info.response")
    assert not bus.has_subscription("system.info.registration.init")
