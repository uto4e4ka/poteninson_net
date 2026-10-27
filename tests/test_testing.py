import asyncio

import pytest

from potehinsonnet.testing import subject_matches


@pytest.mark.parametrize(
    "pattern, subject, expected",
    [
        ("a.b", "a.b", True),
        ("a.b", "a.c", False),
        ("a.*", "a.b", True),
        ("a.*", "a.b.c", False),
        ("a.>", "a.b.c", True),
        ("a.>", "a", False),
        ("*.b", "a.b", True),
        ("a.b.c", "a.b", False),
    ],
)
def test_subject_matches(pattern, subject, expected):
    assert subject_matches(pattern, subject) is expected


async def test_fake_bus_wildcard_delivery(bus, client):
    got = []

    async def handler(data):
        got.append(data)

    await client.subscribe("x.*", handler)
    await client.publish("x.1", {"n": 1})
    await client.publish("y.1", {"n": 2})
    await bus.settle()

    assert got == [{"n": 1}]
    assert bus.messages("x.*") == [{"n": 1}]


async def test_messages_of_one_subscription_are_processed_in_order(bus, client):
    order = []

    async def slow(data):
        order.append(("start", data["n"]))
        await asyncio.sleep(0.01)
        order.append(("end", data["n"]))

    await client.subscribe("q", slow)
    await client.publish("q", {"n": 1})
    await client.publish("q", {"n": 2})
    await bus.settle()

    assert order == [("start", 1), ("end", 1), ("start", 2), ("end", 2)]


async def test_self_unsubscribe_cancels_handler_like_nats_py(bus, client):
    after_unsubscribe = []
    sub = None

    async def handler(data):
        await sub.unsubscribe()
        after_unsubscribe.append(data)  # в nats-py сюда не доходит

    sub = await client.subscribe("once", handler)
    await client.publish("once", {"n": 1})
    await bus.settle()

    assert after_unsubscribe == []
    assert not bus.has_subscription("once")
