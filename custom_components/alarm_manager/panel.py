"""Alarm Manager frontend panel."""

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant


PANEL_URL_PATH = "alarm-manager"
PANEL_NAME = "alarm-manager-panel-v2"
PANEL_TITLE = "Alarm Manager"
PANEL_ICON = "mdi:shield-alert"

FRONTEND_DIR = (
    Path(__file__).parent / "frontend"
)

FRONTEND_FILE = (
    FRONTEND_DIR / "alarm-manager-panel.js"
)

BRAND_DIR = (
    Path(__file__).parent / "brand"
)

BRAND_FILE = (
    BRAND_DIR / "icon.png"
)

STATIC_URL = "/alarm_manager"

# Increase whenever the frontend JavaScript changes.
FRONTEND_VERSION = "0.6.0"


async def async_register_panel(
    hass: HomeAssistant,
) -> None:
    """Register the Alarm Manager panel."""

    if not FRONTEND_FILE.exists():
        return

    static_paths = [
        StaticPathConfig(
            STATIC_URL,
            str(FRONTEND_DIR),
            False,
        )
    ]

    if BRAND_FILE.exists():
        static_paths.append(
            StaticPathConfig(
                f"{STATIC_URL}/brand",
                str(BRAND_DIR),
                False,
            )
        )

    await hass.http.async_register_static_paths(
        static_paths
    )

    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_NAME,
        frontend_url_path=PANEL_URL_PATH,
        module_url=(
            f"{STATIC_URL}/alarm-manager-panel.js"
            f"?v={FRONTEND_VERSION}"
        ),
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
    )


def async_unregister_panel(
    hass: HomeAssistant,
) -> None:
    """Unregister the Alarm Manager panel."""

    frontend.async_remove_panel(
        hass,
        PANEL_URL_PATH,
    )