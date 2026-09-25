"""Config flow for Listening Genome: link to a Music Assistant entry; options for the settings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_MA_ENTRY_ID, DEVICE_NAME, DOMAIN, MA_DOMAIN
from .core.constants import (
    CONF_ENRICH_ENABLED,
    CONF_MIN_SECONDS_PLAYED,
    CONF_OBSCURITY_PERCENTILE,
    CONF_REBUILD_SCHEDULE_HOUR,
    CONF_RECENCY_HALF_LIFE_DAYS,
    HALF_LIFE_DAYS_RANGE,
    MIN_SECONDS_PLAYED_RANGE,
    OBSCURITY_PERCENTILE_CHOICES,
    REBUILD_SCHEDULE_HOUR_RANGE,
)
from .core.service import GenomeServiceSettings

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigEntry, ConfigFlowResult


class ListeningGenomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """
    Pick the Music Assistant entry this integration reads from.

    Only that entry's id is stored. Its URL and token stay in the Music Assistant entry, so
    nothing secret is copied and a re-authenticated MA entry needs no change here. Single
    instance is enforced by ``single_config_entry`` in the manifest.
    """

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ListeningGenomeOptionsFlow:
        """Return the settings flow."""
        return ListeningGenomeOptionsFlow()

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


def _whole_number(value: Any) -> int:
    """Accept 12 or 12.0, reject 12.5: the number selector bounds a value but not its step."""
    number = float(value)
    if not number.is_integer():
        raise vol.Invalid("expected a whole number")
    return int(number)


def _int_in(bounds: tuple[int, int]) -> vol.All:
    """
    A whole number within ``bounds`` (inclusive).

    The selector's bounds are enforced server-side as well as shown in the form: a value out of
    range is rejected before the flow step runs, and nothing is saved.
    """
    low, high = bounds
    return vol.All(
        NumberSelector(
            NumberSelectorConfig(min=low, max=high, step=1, mode=NumberSelectorMode.BOX)
        ),
        _whole_number,
    )


def _options_schema(current: GenomeServiceSettings) -> vol.Schema:
    """The settings form, prefilled with the current values (the fork's defaults if unset)."""
    return vol.Schema(
        {
            vol.Required(CONF_RECENCY_HALF_LIFE_DAYS, default=current.half_life_days): _int_in(
                HALF_LIFE_DAYS_RANGE
            ),
            # only the baseline's own percentiles: the engine scores any other value as 0%
            vol.Required(
                CONF_OBSCURITY_PERCENTILE, default=str(current.obscurity_percentile)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[str(value) for value in OBSCURITY_PERCENTILE_CHOICES],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_OBSCURITY_PERCENTILE,
                )
            ),
            vol.Required(CONF_MIN_SECONDS_PLAYED, default=current.min_seconds_played): _int_in(
                MIN_SECONDS_PLAYED_RANGE
            ),
            vol.Required(
                CONF_REBUILD_SCHEDULE_HOUR, default=current.rebuild_schedule_hour
            ): _int_in(REBUILD_SCHEDULE_HOUR_RANGE),
            vol.Required(CONF_ENRICH_ENABLED, default=current.enrich_enabled): BooleanSelector(),
        }
    )


class ListeningGenomeOptionsFlow(OptionsFlow):
    """
    The settings screen: the fork's engine and schedule settings (Last.fm arrives in 2c).

    Saving reloads the entry (see ``_async_options_updated``), which re-registers the schedules
    and rebuilds when a setting the genome depends on changed.
    """

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the settings form; save what the schema has already validated."""
        if user_input is not None:
            return self.async_create_entry(data=_to_options(user_input))
        current = GenomeServiceSettings.from_options(self.config_entry.options)
        return self.async_show_form(step_id="init", data_schema=_options_schema(current))


def _to_options(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Store every setting with its real type (the percentile arrives as a select string)."""
    return {
        CONF_RECENCY_HALF_LIFE_DAYS: int(user_input[CONF_RECENCY_HALF_LIFE_DAYS]),
        CONF_OBSCURITY_PERCENTILE: int(user_input[CONF_OBSCURITY_PERCENTILE]),
        CONF_MIN_SECONDS_PLAYED: int(user_input[CONF_MIN_SECONDS_PLAYED]),
        CONF_REBUILD_SCHEDULE_HOUR: int(user_input[CONF_REBUILD_SCHEDULE_HOUR]),
        CONF_ENRICH_ENABLED: bool(user_input[CONF_ENRICH_ENABLED]),
    }
