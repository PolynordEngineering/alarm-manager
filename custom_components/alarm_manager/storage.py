"""Persistent storage for Alarm Manager."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN


STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.alarms"


class AlarmStorage:
    """Handle persistent Alarm Manager storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize storage."""

        self._store = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
        )

    async def async_load(self) -> dict[str, Any]:
        """Load stored alarms and history."""

        data = await self._store.async_load()

        if not data:
            return {
                "alarms": {},
                "history": [],
            }

        return {
            "alarms": data.get(
                "alarms",
                {},
            ),
            "history": data.get(
                "history",
                [],
            ),
        }

    async def async_save(
        self,
        alarms: dict[str, Any],
        history: list[dict[str, Any]] | None = None,
    ) -> None:
        """Save alarms and history."""

        await self._store.async_save(
            {
                "alarms": alarms,
                "history": history or [],
            }
        )