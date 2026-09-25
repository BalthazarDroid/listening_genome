"""Tests for the Listening Genome config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.listening_genome.const import CONF_MA_ENTRY_ID, DOMAIN, MA_DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _add_ma_entry(hass: HomeAssistant, entry_id: str, title: str, **kwargs: object) -> None:
    MockConfigEntry(
        domain=MA_DOMAIN,
        title=title,
        entry_id=entry_id,
        # what a real MA entry holds; none of it may leak into ours
        data={"url": f"http://{entry_id}.local:8095", "token": "secret-token"},
        **kwargs,  # type: ignore[arg-type]
    ).add_to_hass(hass)


def _no_setup():  # type: ignore[no-untyped-def]
    return patch("custom_components.listening_genome.async_setup_entry", return_value=True)


async def test_aborts_without_music_assistant(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "ma_not_configured"


async def test_ignored_music_assistant_entry_does_not_count(hass: HomeAssistant) -> None:
    _add_ma_entry(hass, "ignored", "Ignored MA", source=SOURCE_IGNORE)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "ma_not_configured"


async def test_one_music_assistant_entry_confirms_and_stores_only_its_id(
    hass: HomeAssistant,
) -> None:
    _add_ma_entry(hass, "ma-1", "Music Assistant")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"ma_name": "Music Assistant"}

    with _no_setup():
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Listening Genome"
    assert result["data"] == {CONF_MA_ENTRY_ID: "ma-1"}
    [entry] = hass.config_entries.async_entries(DOMAIN)
    assert dict(entry.data) == {CONF_MA_ENTRY_ID: "ma-1"}
    assert dict(entry.options) == {}


async def test_two_music_assistant_entries_show_a_selector(hass: HomeAssistant) -> None:
    _add_ma_entry(hass, "ma-1", "Living room MA")
    _add_ma_entry(hass, "ma-2", "Office MA")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick"
    selector = result["data_schema"].schema[CONF_MA_ENTRY_ID]
    options = selector.config["options"]
    assert options == [
        {"value": "ma-1", "label": "Living room MA"},
        {"value": "ma-2", "label": "Office MA"},
    ]

    with _no_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_MA_ENTRY_ID: "ma-2"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_MA_ENTRY_ID: "ma-2"}


async def test_picking_a_removed_entry_shows_an_error(hass: HomeAssistant) -> None:
    _add_ma_entry(hass, "ma-1", "Living room MA")
    _add_ma_entry(hass, "ma-2", "Office MA")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    await hass.config_entries.async_remove("ma-2")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MA_ENTRY_ID: "ma-2"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "ma_entry_missing"}


async def test_single_instance_only(hass: HomeAssistant) -> None:
    _add_ma_entry(hass, "ma-1", "Music Assistant")
    MockConfigEntry(domain=DOMAIN, data={CONF_MA_ENTRY_ID: "ma-1"}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
