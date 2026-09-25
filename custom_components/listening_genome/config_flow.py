"""Config flow for Listening Genome: link the integration to a Music Assistant entry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_MA_ENTRY_ID, DEVICE_NAME, DOMAIN, MA_DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry, ConfigFlowResult


class ListeningGenomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """
    Pick the Music Assistant entry this integration reads from.

    Only that entry's id is stored. Its URL and token stay in the Music Assistant entry, so
    nothing secret is copied and a re-authenticated MA entry needs no change here. Single
    instance is enforced by ``single_config_entry`` in the manifest.
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._ma_entry: ConfigEntry | None = None

    def _ma_entries(self) -> list[ConfigEntry]:
        """Return the configured (not ignored) Music Assistant entries."""
        return self.hass.config_entries.async_entries(MA_DOMAIN, include_ignore=False)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Route to a confirm or pick step depending on how many MA entries exist."""
        entries = self._ma_entries()
        if not entries:
            return self.async_abort(reason="ma_not_configured")
        if len(entries) == 1:
            self._ma_entry = entries[0]
            return await self.async_step_confirm()
        return await self.async_step_pick()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm linking to the only Music Assistant entry."""
        assert self._ma_entry is not None
        if user_input is not None:
            return self._create(self._ma_entry)
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"ma_name": self._ma_entry.title},
        )

    async def async_step_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose one of several Music Assistant entries."""
        entries = {entry.entry_id: entry for entry in self._ma_entries()}
        errors: dict[str, str] = {}
        if user_input is not None:
            chosen = entries.get(user_input[CONF_MA_ENTRY_ID])
            if chosen is not None:
                return self._create(chosen)
            # the entry was removed while the form was open
            errors["base"] = "ma_entry_missing"
        schema = vol.Schema(
            {
                vol.Required(CONF_MA_ENTRY_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=entry_id, label=entry.title)
                            for entry_id, entry in entries.items()
                        ],
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="pick", data_schema=schema, errors=errors)

    def _create(self, ma_entry: ConfigEntry) -> ConfigFlowResult:
        """Create the entry, storing only the Music Assistant entry's id."""
        return self.async_create_entry(
            title=DEVICE_NAME, data={CONF_MA_ENTRY_ID: ma_entry.entry_id}
        )
