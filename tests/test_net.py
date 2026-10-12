from datetime import datetime

import pytest

from potehinsonnet.net import ERROR_KEY, NatsRequestError


async def test_publish_serializes_datetime(bus, client):
    moment = datetime(2026, 1, 2, 3, 4, 5)

    await client.publish("t", {"time": moment})

    assert bus.messages("t") == [{"time": "2026-01-02T03:04:05"}]


async def test_request_returns_handler_response(client):
    async def handler(data):
        return {"echo": data["v"], "time": datetime(2026, 1, 1)}

    await client.subscribe("svc", handler)

    response = await client.request("svc", {"v": 42})

    assert response == {"echo": 42, "time": "2026-01-01T00:00:00"}


async def test_handler_returning_none_does_not_reply(client):
    async def handler(data):
        return None

    await client.subscribe("svc", handler)

    with pytest.raises(TimeoutError):
        await client.request("svc", {}, timeout=0.05)


async def test_handler_error_is_returned_to_requester(client):
    async def handler(data):
        raise ValueError("boom")

    await client.subscribe("svc", handler)

    with pytest.raises(NatsRequestError, match="ValueError: boom"):
        await client.request("svc", {})


async def test_handler_error_on_publish_does_not_break_subscription(bus, client):
    calls = []

    async def handler(data):
        calls.append(data)
        if data.get("fail"):
            raise RuntimeError("fail")

    await client.subscribe("svc", handler)
    await client.publish("svc", {"fail": True})
    await client.publish("svc", {"fail": False})
    await bus.settle()

    assert calls == [{"fail": True}, {"fail": False}]


async def test_error_key_is_reserved(client):
    async def handler(data):
        return {ERROR_KEY: "something"}

    await client.subscribe("svc", handler)

    with pytest.raises(NatsRequestError):
        await client.request("svc", {})


async def test_async_context_manager(bus):
    client = bus.client()

    async with client as entered:
        assert entered is client
