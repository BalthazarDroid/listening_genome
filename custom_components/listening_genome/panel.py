"""
The sidebar panel: serve the built frontend and register it with Home Assistant.

The panel is one ES module (``frontend/listening-genome-panel.js``, built from ``/frontend``
in the repository and committed, since HACS installs the repository as it is) plus the page's
two fonts. It talks to the integration only through ``hass.callWS`` - the websocket commands
in ``websocket_api.py`` - so it needs no token and no URL of its own.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PANEL_URL_PATH = "listening-genome"
PANEL_ELEMENT = "listening-genome-panel"
PANEL_TITLE = "Listening Genome"
PANEL_ICON = "mdi:dna"
STATIC_URL = f"/{DOMAIN}_static"
FRONTEND_DIR = Path(__file__).parent / "frontend"
MODULE_FILE = "listening-genome-panel.js"

_STATIC_REGISTERED = f"{DOMAIN}_static_registered"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Serve the frontend (once per Home Assistant run) and add the sidebar entry."""
    if not hass.data.get(_STATIC_REGISTERED):
        # static paths cannot be unregistered, so they are registered once and outlive reloads
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False)]
        )
        hass.data[_STATIC_REGISTERED] = True
    # the module's hash in its URL: a browser that cached an older build fetches the new one
    version = await hass.async_add_executor_job(_file_hash, FRONTEND_DIR / MODULE_FILE)
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_ELEMENT,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=f"{STATIC_URL}/{MODULE_FILE}?v={version}",
        embed_iframe=False,
        require_admin=False,
        config={"static_base": STATIC_URL},
    )


def async_remove_panel(hass: HomeAssistant) -> None:
    """Take the sidebar entry away (the entry unloaded)."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
