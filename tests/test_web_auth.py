import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram_voice_transcriber.web_auth import WebAuthManager, AuthState


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.is_user_authorized = AsyncMock(return_value=False)
    client.send_code_request = AsyncMock()
    client.sign_in = AsyncMock()
    client.get_me = AsyncMock(return_value=MagicMock(id=123, first_name="Test"))
    return client


def test_auth_manager_initial_state():
    manager = WebAuthManager()
    assert manager.state == AuthState.NEEDS_CREDENTIALS


def test_auth_manager_set_credentials():
    manager = WebAuthManager()
    manager.set_credentials(api_id=123456, api_hash="abc123")
    assert manager.state == AuthState.NEEDS_PHONE
    assert manager.api_id == 123456


@pytest.mark.asyncio
async def test_auth_manager_send_code(mock_client):
    manager = WebAuthManager()
    manager.set_credentials(api_id=123456, api_hash="abc123")
    manager._client = mock_client

    await manager.send_code("+1234567890")

    mock_client.send_code_request.assert_called_once_with("+1234567890")
    assert manager.state == AuthState.NEEDS_CODE
