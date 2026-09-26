"""
Actions: import Last.fm history, or an Apple Music export already on disk.

Until the panel (Phase 3) gives these a page, the actions are how an import is started - from
Developer tools > Actions, a script, or an automation. They return at once; the outcome is the
``lastfm_import`` / ``apple_import`` job (and the Home Assistant log).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_DRY_RUN,
    ATTR_MAX_PAGES,
    ATTR_PATH,
    DOMAIN,
    SERVICE_IMPORT_APPLE_CSV,
    SERVICE_IMPORT_FORK_EXPORT,
    SERVICE_IMPORT_LASTFM,
)

if TYPE_CHECKING:
    from .runtime import ListeningGenomeData

IMPORT_LASTFM_SCHEMA = vol.Schema({vol.Optional(ATTR_MAX_PAGES, default=0): cv.positive_int})
IMPORT_APPLE_SCHEMA = vol.Schema({vol.Required(ATTR_PATH): cv.string})
IMPORT_FORK_SCHEMA = vol.Schema(
    {vol.Required(ATTR_PATH): cv.string, vol.Optional(ATTR_DRY_RUN, default=False): cv.boolean}
)


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register the integration's actions (once, from ``async_setup``)."""

    def _runtime() -> ListeningGenomeData:
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_loaded")
        return entries[0].runtime_data

    async def import_lastfm(call: ServiceCall) -> None:
        runtime = _runtime()
        if not runtime.settings.lastfm_configured:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="lastfm_not_configured"
            )
        if not runtime.async_request_lastfm_import(
            max_pages=call.data[ATTR_MAX_PAGES], rebuild=True
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="lastfm_already_running"
            )

    async def import_apple_csv(call: ServiceCall) -> None:
        runtime = _runtime()
        path = call.data[ATTR_PATH]
        if not hass.config.is_allowed_path(path):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="path_not_allowed",
                translation_placeholders={"path": path},
            )
        if not await hass.async_add_executor_job(os.path.isfile, path):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="file_not_found",
                translation_placeholders={"path": path},
            )
        runtime.async_request_apple_import(path, os.path.basename(path), cleanup=False)

    async def import_fork_export(call: ServiceCall) -> ServiceResponse:
        runtime = _runtime()
        path = call.data[ATTR_PATH]
        _check_readable(path)
        if not await hass.async_add_executor_job(os.path.isfile, path):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="file_not_found",
                translation_placeholders={"path": path},
            )
        report = await runtime.operations.import_fork_live_plays(
            path, dry_run=call.data[ATTR_DRY_RUN]
        )
        if report["added"]:
            runtime.async_request_rebuild("fork plays imported")
        return report

    def _check_readable(path: str) -> None:
        if not hass.config.is_allowed_path(path):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="path_not_allowed",
                translation_placeholders={"path": path},
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_IMPORT_FORK_EXPORT,
        import_fork_export,
        schema=IMPORT_FORK_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_IMPORT_LASTFM, import_lastfm, schema=IMPORT_LASTFM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_IMPORT_APPLE_CSV, import_apple_csv, schema=IMPORT_APPLE_SCHEMA
    )
