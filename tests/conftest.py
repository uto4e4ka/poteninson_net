import pytest

from potehinsonnet.net_models.discord_models import Channel, ExecutedCommand, Guild, User
from potehinsonnet.net_models.system_models import Service
from potehinsonnet.testing import FakeNats


@pytest.fixture
def bus() -> FakeNats:
    return FakeNats()


@pytest.fixture
def client(bus):
    return bus.client()


@pytest.fixture
def plugin() -> Service:
    return Service(name="test_plugin", label="Test", author="me", version="1.0")


def make_executed(tag: str = "x", entity_id: str = "E1", service: str = "test_plugin", **kwargs) -> ExecutedCommand:
    return ExecutedCommand(
        service=service,
        tag=tag,
        entity_id=entity_id,
        reply_to=f"discord.command.reply.{entity_id}",
        user=User(id=1, name="user"),
        guild=Guild(id=10, name="guild"),
        channel=Channel(id=100, name="general"),
        **kwargs,
    )
