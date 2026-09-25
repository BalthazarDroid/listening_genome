"""Config flow for Listening Genome: link to a Music Assistant entry; options for the settings."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.loader import async_get_integration

from .const import CONF_MA_ENTRY_ID, DEVICE_NAME, DOMAIN, MA_DOMAIN
from .core.constants import (
    CONF_ENRICH_ENABLED,
    CONF_LASTFM_API_KEY,
    CONF_LASTFM_POLL_ENABLED,
    CONF_LASTFM_POLL_INTERVAL_HOURS,
    CONF_LASTFM_USERNAME,
    CONF_MIN_SECONDS_PLAYED,
    CONF_OBSCURITY_PERCENTILE,
    CONF_REBUILD_SCHEDULE_HOUR,
    CONF_RECENCY_HALF_LIFE_DAYS,
    HALF_LIFE_DAYS_RANGE,
    LASTFM_API_KEY_PATTERN,
    LASTFM_POLL_INTERVAL_HOURS_RANGE,
    LASTFM_RATE_LIMIT,
    LASTFM_RATE_PERIOD_SECONDS,
    MIN_SECONDS_PLAYED_RANGE,
    OBSCURITY_PERCENTILE_CHOICES,
    REBUILD_SCHEDULE_HOUR_RANGE,
)
from .core.errors import LastfmApiError
from .core.http import AiohttpClient, user_agent
from .core.service import GenomeServiceSettings
from .importers.lastfm import LastfmImporter, describe_fetch_error

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


# the options form's Last.fm group; stored flat, next to the other settings
SECTION_LASTFM = "lastfm"


def _options_schema(current: GenomeServiceSettings) -> vol.Schema:
    """
    The settings form, prefilled with the current values (the fork's defaults if unset).

    The Last.fm API key is never sent back to the browser: the field is always empty, and
    leaving it empty keeps the stored key.
    """
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
            vol.Required(SECTION_LASTFM): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_LASTFM_USERNAME, default=current.lastfm_username
                        ): TextSelector(),
                        vol.Optional(CONF_LASTFM_API_KEY, default=""): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.PASSWORD)
                        ),
                        vol.Required(
                            CONF_LASTFM_POLL_ENABLED, default=current.lastfm_poll_enabled
                        ): BooleanSelector(),
                        vol.Required(
                            CONF_LASTFM_POLL_INTERVAL_HOURS,
                            default=current.lastfm_poll_interval_hours,
                        ): _int_in(LASTFM_POLL_INTERVAL_HOURS_RANGE),
                    }
                ),
                {"collapsed": not current.lastfm_configured},
            ),
        }
    )


class ListeningGenomeOptionsFlow(OptionsFlow):
    """
    The settings screen: the fork's engine and schedule settings, and Last.fm.

    Saving reloads the entry (see ``_async_options_updated``), which re-registers the schedules
    and rebuilds when a setting the genome depends on changed.
    """

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the settings form; check new Last.fm credentials with Last.fm before saving."""
        current = GenomeServiceSettings.from_options(self.config_entry.options)
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"reason": ""}
        if user_input is not None:
            options = _to_options(user_input, current)
            error = _lastfm_form_error(options)
            if error is None and _lastfm_changed(options, current) and options[CONF_LASTFM_API_KEY]:
                reason = await self._check_lastfm(
                    options[CONF_LASTFM_USERNAME], options[CONF_LASTFM_API_KEY]
                )
                if reason is not None:
                    error = "lastfm_rejected"
                    placeholders["reason"] = reason
            if error is None:
                return self.async_create_entry(data=options)
            errors["base"] = error
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(current),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def _check_lastfm(self, username: str, api_key: str) -> str | None:
        """Ask Last.fm for one scrobble; return why it refused, or ``None`` if it answered."""
        integration = await async_get_integration(self.hass, DOMAIN)
        client = AiohttpClient(
            async_get_clientsession(self.hass),
            rate_limit=LASTFM_RATE_LIMIT,
            period=LASTFM_RATE_PERIOD_SECONDS,
            user_agent=user_agent(str(integration.version)),
        )
        try:
            await LastfmImporter(client, username, api_key).fetch_recent(1, limit=1)
        except LastfmApiError as err:
            return str(err)
        except Exception as err:  # network trouble: say so without echoing the request URL
            return describe_fetch_error(err)
        return None


def _to_options(user_input: Mapping[str, Any], current: GenomeServiceSettings) -> dict[str, Any]:
    """
    Store every setting flat, with its real type (the percentile arrives as a select string).

    An empty API key field keeps the stored key; clearing the username clears both.
    """
    lastfm = user_input.get(SECTION_LASTFM) or {}
    username = str(lastfm.get(CONF_LASTFM_USERNAME) or "").strip()
    api_key = str(lastfm.get(CONF_LASTFM_API_KEY) or "").strip() or current.lastfm_api_key
    if not username:
        api_key = ""
    return {
        CONF_RECENCY_HALF_LIFE_DAYS: int(user_input[CONF_RECENCY_HALF_LIFE_DAYS]),
        CONF_OBSCURITY_PERCENTILE: int(user_input[CONF_OBSCURITY_PERCENTILE]),
        CONF_MIN_SECONDS_PLAYED: int(user_input[CONF_MIN_SECONDS_PLAYED]),
        CONF_REBUILD_SCHEDULE_HOUR: int(user_input[CONF_REBUILD_SCHEDULE_HOUR]),
        CONF_ENRICH_ENABLED: bool(user_input[CONF_ENRICH_ENABLED]),
        CONF_LASTFM_USERNAME: username,
        CONF_LASTFM_API_KEY: api_key,
        CONF_LASTFM_POLL_ENABLED: bool(lastfm.get(CONF_LASTFM_POLL_ENABLED, False)),
        CONF_LASTFM_POLL_INTERVAL_HOURS: int(
            lastfm.get(CONF_LASTFM_POLL_INTERVAL_HOURS) or current.lastfm_poll_interval_hours
        ),
    }


def _lastfm_form_error(options: Mapping[str, Any]) -> str | None:
    """A problem the form itself can see, without asking Last.fm; the key is never echoed."""
    api_key = options[CONF_LASTFM_API_KEY]
    if api_key and not re.match(LASTFM_API_KEY_PATTERN, api_key):
        return "lastfm_key_format"
    if options[CONF_LASTFM_USERNAME] and not api_key:
        return "lastfm_key_missing"
    if options[CONF_LASTFM_POLL_ENABLED] and not options[CONF_LASTFM_USERNAME]:
        return "lastfm_poll_needs_account"
    return None


def _lastfm_changed(options: Mapping[str, Any], current: GenomeServiceSettings) -> bool:
    return (
        options[CONF_LASTFM_USERNAME] != current.lastfm_username
        or options[CONF_LASTFM_API_KEY] != current.lastfm_api_key
    )
