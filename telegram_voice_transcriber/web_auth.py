"""Web-compatible Telegram authentication manager."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Any

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError


class AuthState(Enum):
    NEEDS_CREDENTIALS = auto()
    NEEDS_PHONE = auto()
    NEEDS_CODE = auto()
    NEEDS_2FA = auto()
    AUTHENTICATED = auto()
    ERROR = auto()


@dataclass
class WebAuthManager:
    """Manages Telegram authentication flow for web UI."""

    api_id: Optional[int] = None
    api_hash: Optional[str] = None
    phone: Optional[str] = None
    session_path: Path = field(default_factory=lambda: Path(".data/web.session"))
    state: AuthState = AuthState.NEEDS_CREDENTIALS
    error_message: Optional[str] = None
    user_info: Optional[dict] = None
    _client: Optional[TelegramClient] = field(default=None, repr=False)

    def set_credentials(self, api_id: int, api_hash: str) -> None:
        """Set API credentials and advance state."""
        self.api_id = api_id
        self.api_hash = api_hash
        self.state = AuthState.NEEDS_PHONE

    async def connect(self) -> None:
        """Initialize and connect the Telegram client."""
        if self._client is None:
            self.session_path.parent.mkdir(parents=True, exist_ok=True)
            self._client = TelegramClient(
                str(self.session_path), self.api_id, self.api_hash
            )
        await self._client.connect()

        if await self._client.is_user_authorized():
            me = await self._client.get_me()
            self.user_info = {"id": me.id, "name": getattr(me, "first_name", str(me.id))}
            self.state = AuthState.AUTHENTICATED

    async def send_code(self, phone: str) -> None:
        """Send verification code to phone number."""
        self.phone = phone
        await self._client.send_code_request(phone)
        self.state = AuthState.NEEDS_CODE

    async def verify_code(self, code: str) -> None:
        """Verify the received code."""
        try:
            await self._client.sign_in(phone=self.phone, code=code)
            me = await self._client.get_me()
            self.user_info = {"id": me.id, "name": getattr(me, "first_name", str(me.id))}
            self.state = AuthState.AUTHENTICATED
        except SessionPasswordNeededError:
            self.state = AuthState.NEEDS_2FA

    async def verify_2fa(self, password: str) -> None:
        """Verify 2FA password."""
        await self._client.sign_in(password=password)
        me = await self._client.get_me()
        self.user_info = {"id": me.id, "name": getattr(me, "first_name", str(me.id))}
        self.state = AuthState.AUTHENTICATED

    async def disconnect(self) -> None:
        """Disconnect the client."""
        if self._client:
            await self._client.disconnect()

    @property
    def client(self) -> Optional[TelegramClient]:
        """Get the underlying Telegram client."""
        return self._client
