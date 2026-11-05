from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_logs_fail_explicitly_instead_of_returning_demo_output(monkeypatch):
    from routers.logs import get_logs
    monkeypatch.setattr('routers.logs.agent_client.get_resource_logs', AsyncMock(side_effect=ConnectionError('offline')))
    with pytest.raises(HTTPException) as error:
        await get_logs('demo.service', tail=20, since=None, until=None, level=None, user={'role': 'admin'})
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_systemd_ui_id_is_translated_for_log_rpc(monkeypatch):
    from services.agent_client import AgentClient
    client = AgentClient()
    call = AsyncMock(return_value=[])
    monkeypatch.setattr(client, 'call', call)
    await client.get_resource_logs('systemd-demo', 20)
    call.assert_awaited_once_with('resource.logs', {'resource_id': 'demo.service', 'tail': 20})


@pytest.mark.asyncio
async def test_service_filter_is_applied_without_provider(monkeypatch):
    from routers.resources import ResourceResponse, list_resources
    service = ResourceResponse(id='systemd-demo', name='demo', type='service', resource_class='APP', provider='systemd', state='running', health_score=100, managed=True, updated_at='2026-11-05')
    cursor = AsyncMock()
    cursor.fetchall.return_value = []
    database = AsyncMock()
    database.execute.return_value = cursor
    monkeypatch.setattr('routers.resources.get_control_db', AsyncMock(return_value=database))
    monkeypatch.setattr('routers.resources._get_live_systemd_services', AsyncMock(return_value=[service]))
    result = await list_resources(provider=None, resource_class='CORE', managed=None, refresh=False, user={'role': 'admin'})
    assert result == []


@pytest.mark.asyncio
async def test_operator_cannot_restart_a_system_service(monkeypatch):
    from routers.resources import ActionRequest, execute_action
    cursor = AsyncMock()
    cursor.fetchone.return_value = None
    database = AsyncMock()
    database.execute.return_value = cursor
    monkeypatch.setattr('routers.resources.get_control_db', AsyncMock(return_value=database))
    rpc = AsyncMock(return_value={"success": True})
    monkeypatch.setattr('routers.resources.agent_client.execute_action', rpc)
    with pytest.raises(HTTPException) as error:
        await execute_action('systemd-bluetooth', ActionRequest(action='restart'), {'id': 2, 'role': 'operator'})
    assert error.value.status_code == 403
    rpc.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['admin', 'operator'])
async def test_systemd_named_unit_preserves_real_unit_and_system_role(monkeypatch, role):
    from routers.resources import ActionRequest, execute_action
    cursor = AsyncMock()
    cursor.fetchone.return_value = None
    database = AsyncMock()
    database.execute.return_value = cursor
    monkeypatch.setattr('routers.resources.get_control_db', AsyncMock(return_value=database))
    rpc = AsyncMock(return_value={'success': False, 'message': 'test stops after target validation'})
    monkeypatch.setattr('routers.resources.agent_client.execute_action', rpc)
    try:
        await execute_action('systemd-systemd-timesyncd', ActionRequest(action='restart'), {'id': 2, 'role': role})
    except HTTPException as error:
        if role == 'operator':
            assert error.status_code == 403
    if role == 'operator':
        rpc.assert_not_awaited()
    else:
        rpc.assert_awaited_once_with('systemd-timesyncd.service', 'restart', None)
