import asyncio
from unittest.mock import AsyncMock

import pytest

from routers import sse as sse_router
from services.sse import Channels, SSEManager


@pytest.mark.asyncio
async def test_sse_manager_subscription_delivery_and_cleanup():
    manager = SSEManager()
    first = await manager.connect("first", 1)
    second = await manager.connect("second", 2)
    await manager.subscribe("first", Channels.ALERTS)
    await manager.subscribe("second", Channels.ALERTS)

    await manager.broadcast(Channels.ALERTS, "alert.created", {"id": 7})

    first_message = await asyncio.wait_for(first.queue.get(), timeout=0.1)
    second_message = await asyncio.wait_for(second.queue.get(), timeout=0.1)
    assert first_message["event"] == "alert.created"
    assert first_message["data"] == {"id": 7}
    assert second_message["channel"] == Channels.ALERTS
    assert manager.client_count == 2
    assert manager.get_channel_clients(Channels.ALERTS) == 2

    await manager.unsubscribe("second", Channels.ALERTS)
    await manager.disconnect("first")
    assert manager.client_count == 1
    assert manager.get_channel_clients(Channels.ALERTS) == 0


@pytest.mark.asyncio
async def test_sse_manager_direct_message_format_and_keepalive(monkeypatch):
    manager = SSEManager()
    client = await manager.connect("client", 1)
    await manager.send_to_client("client", "status", ["ready"])
    generator = manager.event_generator(client)

    assert await anext(generator) == 'event: status\ndata: ["ready"]\n\n'

    async def timeout(coroutine, **_kwargs):
        coroutine.close()
        raise asyncio.TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", timeout)
    assert await anext(generator) == ": keepalive\n\n"
    await generator.aclose()


class _Request:
    query_params = {}
    is_disconnected = AsyncMock(return_value=False)


@pytest.fixture(autouse=True)
async def reset_global_sse_manager():
    manager = sse_router.sse_manager
    manager._clients.clear()
    manager._channels.clear()
    yield
    manager._clients.clear()
    manager._channels.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("factory", "channel", "expected"),
    [
        (
            lambda request: sse_router.telemetry_stream(request, {"id": 1}),
            Channels.TELEMETRY,
            '"client_id"',
        ),
        (
            lambda request: sse_router.resources_stream(request, {"id": 1}),
            Channels.RESOURCES,
            '"client_id"',
        ),
        (
            lambda request: sse_router.logs_stream("svc.service", request, {"id": 1}),
            Channels.logs("svc.service"),
            '"resource_id": "svc.service"',
        ),
        (
            lambda request: sse_router.job_stream("job-1", request, {"id": 1}),
            Channels.job("job-1"),
            '"job_id": "job-1"',
        ),
        (
            lambda request: sse_router.alerts_stream(request, {"id": 1}),
            Channels.ALERTS,
            '"client_id"',
        ),
    ],
)
async def test_specialized_streams_subscribe_emit_and_disconnect(
    factory, channel, expected
):
    response = await factory(_Request())

    chunk = await anext(response.body_iterator)
    assert expected in chunk
    assert sse_router.sse_manager.get_channel_clients(channel) == 1

    await response.body_iterator.aclose()
    assert sse_router.sse_manager.client_count == 0


@pytest.mark.asyncio
async def test_main_stream_defaults_and_forwards_events():
    request = _Request()
    response = await sse_router.stream(request, {"id": 1})
    client = next(iter(sse_router.sse_manager._clients.values()))
    assert client.subscriptions == {
        Channels.TELEMETRY,
        Channels.RESOURCES,
        Channels.ALERTS,
    }

    await sse_router.sse_manager.broadcast(
        Channels.TELEMETRY, "telemetry", {"cpu": 12}
    )
    assert await anext(response.body_iterator) == (
        'event: telemetry\ndata: {"cpu": 12}\n\n'
    )

    await response.body_iterator.aclose()
    assert sse_router.sse_manager.client_count == 0
