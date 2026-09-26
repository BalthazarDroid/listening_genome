"""
Live capture: record every track Music Assistant plays, as it plays.

Opens this integration's own websocket session to the Music Assistant server the linked MA
config entry points at (its URL and token are read from that entry at every connect, never
copied), subscribes to ``media_item_played``, and folds the progress reports into listens with
:class:`~.core.live.LivePlayTracker`.

Why a session of our own, when Home Assistant's Music Assistant integration already has one:
that client lives in the other integration's private runtime data, which can change shape in
any Home Assistant release. A second websocket to the same server costs nothing and depends on
nothing but the MA client library's public API.

The connection is kept up by reconnect timers with capped exponential backoff: Music Assistant restarting,
updating, or the add-on being stopped are all normal, and none of them may take the integration
down. While MA is unreachable, nothing is captured - plays made meanwhile reach the genome only
through Last.fm, if MA scrobbles there.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from music_assistant_client import MusicAssistantClient
from music_assistant_models.enums import EventType

from .const import CONF_MA_ENTRY_ID, MA_DOMAIN
from .core.constants import LOGGER
from .core.live import LivePlayTracker, PlayReport

if TYPE_CHECKING:
    from collections.abc import Callable

    from aiohttp import ClientSession
    from homeassistant.config_entries import ConfigEntry
    from music_assistant_models.event import MassEvent

    from .core.live import CapturedListen
    from .core.operations import GenomeOperations

    ClientFactory = Callable[[str, ClientSession, str | None], MusicAssistantClient]

#: reconnect delays: start quick (an MA restart takes seconds), back off to five minutes
RECONNECT_MIN_SECONDS = 5.0
RECONNECT_MAX_SECONDS = 300.0

#: how often players that went quiet have their open play written out
IDLE_FLUSH_INTERVAL = timedelta(minutes=1)

#: MA not configured / not found: check again this often
MA_MISSING_RETRY_SECONDS = 60.0

_PLAYER_EVENTS = (EventType.PLAYER_ADDED, EventType.PLAYER_UPDATED)


def _default_client_factory(
    url: str, session: ClientSession, token: str | None
) -> MusicAssistantClient:
    return MusicAssistantClient(url, session, token=token)


@dataclass(slots=True)
class CaptureStatus:
    """What the connection is doing, for the diagnostic sensor and the panel."""

    connected: bool = False
    server_version: str | None = None
    #: why the last attempt failed (never contains the token: only the exception's class and
    #: the MA client's own message, which does not include it)
    last_error: str | None = None
    plays_captured: int = 0
    last_play: str | None = None
    last_play_at: int | None = None
    connected_since: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """The ``listening_genome/live`` payload."""
        return {
            "connected": self.connected,
            "server_version": self.server_version,
            "last_error": self.last_error,
            "plays_captured": self.plays_captured,
            "last_play": self.last_play,
            "last_play_at": self.last_play_at,
            "connected_since": self.connected_since,
        }


@dataclass(slots=True)
class MusicAssistantCapture:
    """Keep a session to Music Assistant open and record what it plays."""

    hass: HomeAssistant
    entry: ConfigEntry
    operations: GenomeOperations
    #: ``None``: :func:`_default_client_factory`, looked up at connect time (tests patch it)
    client_factory: ClientFactory | None = None
    clock: Callable[[], float] = time.time
    tracker: LivePlayTracker = field(default_factory=LivePlayTracker)
    status: CaptureStatus = field(default_factory=CaptureStatus)
    player_names: dict[str, str] = field(default_factory=dict)
    _task: asyncio.Task[None] | None = None
    _client: MusicAssistantClient | None = None
    _unsub_flush: CALLBACK_TYPE | None = None
    _unsub_retry: CALLBACK_TYPE | None = None
    _retry_delay: float = RECONNECT_MIN_SECONDS
    _stopped: bool = False
    _writes: set[asyncio.Task[Any]] = field(default_factory=set)
    _listeners: list[Callable[[], None]] = field(default_factory=list)

    @callback
    def async_start(self) -> None:
        """Connect now (and again whenever the connection ends); start the idle-flush timer."""
        self._stopped = False
        self._attempt()
        self._unsub_flush = async_track_time_interval(
            self.hass,
            self._handle_flush_interval,
            IDLE_FLUSH_INTERVAL,
            name="Listening Genome idle flush",
            cancel_on_shutdown=True,
        )

    async def async_stop(self) -> None:
        """
        Close the connection, then write every play still open and wait for pending writes.

        Called on unload and when Home Assistant stops, BEFORE the store closes: the writes
        need it (see ``ListeningGenomeData.async_close``).
        """
        self._stopped = True
        if self._unsub_flush is not None:
            self._unsub_flush()
            self._unsub_flush = None
        if self._unsub_retry is not None:
            self._unsub_retry()
            self._unsub_retry = None
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._write(self.tracker.flush_all(self.clock()))
        if self._writes:
            await asyncio.gather(*self._writes, return_exceptions=True)

    @callback
    def async_add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """Call ``update_callback`` whenever :attr:`status` changes; return a remover."""
        self._listeners.append(update_callback)

        def remove() -> None:
            self._listeners.remove(update_callback)

        return remove

    @property
    def client(self) -> MusicAssistantClient | None:
        """The connected client, or ``None`` while Music Assistant is not connected."""
        return self._client if self.status.connected else None

    def player_name(self, player_id: str) -> str | None:
        """The display name MA last gave a player (the store's ``player_name_resolver``)."""
        return self.player_names.get(player_id)

    @callback
    def _attempt(self, _now: Any = None) -> None:
        """
        Start one connection attempt (a session that lasts until the connection ends).

        Between attempts nothing runs: the next one is a timer, not a sleeping task, so a
        Music Assistant that is down for a day costs nothing, and nothing lingers for Home
        Assistant to wait on at shutdown.
        """
        if self._unsub_retry is not None:
            # called early (not by its own timer): that timer must not start a second session
            self._unsub_retry()
            self._unsub_retry = None
        if self._stopped or (self._task is not None and not self._task.done()):
            return
        ma_entry = self.hass.config_entries.async_get_entry(self.entry.data[CONF_MA_ENTRY_ID])
        if ma_entry is None and self._relink():
            # connect to the replacement now. Relying on the data change to reload the
            # integration left capture dead when the relink happened during setup (no update
            # listener yet, so no reload - and no retry either); the update listener now
            # leaves a link-only change alone, since the capture follows it here itself
            ma_entry = self.hass.config_entries.async_get_entry(self.entry.data[CONF_MA_ENTRY_ID])
        url = ma_entry.data.get(CONF_URL) if ma_entry is not None else None
        if not url or ma_entry is None:
            self._set_disconnected(
                "The linked Music Assistant integration was not found; plays are not being captured"
            )
            self._schedule_retry(MA_MISSING_RETRY_SECONDS)
            return
        self._task = self.entry.async_create_background_task(
            self.hass,
            self._session_then_retry(url, ma_entry.data.get(CONF_TOKEN)),
            "Listening Genome: Music Assistant live capture",
        )

    @callback
    def _relink(self) -> bool:
        """
        The linked Music Assistant entry is gone: follow its replacement if there is exactly one.

        Swapping Music Assistant add-ons (the DEV server back to the regular one) means deleting
        one Music Assistant entry and adding another - one at a time, so the players keep their
        entity ids. The new entry has a new id. With exactly one Music Assistant entry left, it
        can only be the replacement, so the link moves to it rather than capture stopping until
        someone notices. With none, or several, nothing is guessed (Reconfigure picks one).
        """
        candidates = self.hass.config_entries.async_entries(MA_DOMAIN, include_ignore=False)
        if len(candidates) != 1:
            return False
        replacement = candidates[0]
        LOGGER.warning(
            "The linked Music Assistant entry was removed; now following %r instead",
            replacement.title,
        )
        self.hass.config_entries.async_update_entry(
            self.entry, data={**self.entry.data, CONF_MA_ENTRY_ID: replacement.entry_id}
        )
        return True

    async def _session_then_retry(self, url: str, token: str | None) -> None:
        listened_for = await self._session(url, token)
        # a session that stayed up a while was a working connection that later dropped: retry
        # quickly. One that failed straight away backs off, doubling up to five minutes.
        if listened_for > RECONNECT_MAX_SECONDS:
            self._retry_delay = RECONNECT_MIN_SECONDS
        delay = self._retry_delay
        self._retry_delay = min(self._retry_delay * 2, RECONNECT_MAX_SECONDS)
        self._schedule_retry(delay)

    @callback
    def _schedule_retry(self, delay: float) -> None:
        if self._stopped:
            return
        self._unsub_retry = async_call_later(self.hass, delay, self._attempt)

    async def _session(self, url: str, token: str | None) -> float:
        """Run one connection until it ends; return how long it was connected (seconds)."""
        session = async_get_clientsession(self.hass)
        factory = self.client_factory or _default_client_factory
        unsubscribers: list[Callable[[], None]] = []
        connected_at: float | None = None
        init_ready = asyncio.Event()
        client: MusicAssistantClient | None = None
        try:
            # inside the try: a client that cannot even be built must still end in a retry
            client = factory(url, session, token)
            unsubscribers.append(
                client.subscribe(self._on_media_item_played, EventType.MEDIA_ITEM_PLAYED)
            )
            unsubscribers.append(client.subscribe(self._on_player_event, _PLAYER_EVENTS))
            await client.connect()
            connected_at = self.clock()
            info = client.server_info
            self._client = client
            self.status.connected = True
            self.status.server_version = info.server_version if info is not None else None
            self.status.last_error = None
            self.status.connected_since = int(connected_at)
            self._notify()
            LOGGER.info(
                "Live capture connected to Music Assistant %s at %s",
                self.status.server_version,
                url,
            )
            names_task = self.entry.async_create_background_task(
                self.hass,
                self._refresh_player_names(client, init_ready),
                "Listening Genome: Music Assistant player names",
            )
            try:
                await client.start_listening(init_ready)
            finally:
                names_task.cancel()
            reason = "Music Assistant closed the connection"
        except asyncio.CancelledError:
            raise
        except Exception as err:  # every failure is "retry later", whatever its type
            reason = f"{type(err).__name__}: {err}" if str(err) else type(err).__name__
        finally:
            for unsubscribe in unsubscribers:
                with contextlib.suppress(ValueError):
                    unsubscribe()
            self._client = None
            if client is not None:
                with contextlib.suppress(Exception):
                    await client.disconnect()
        was_connected = self.status.connected
        self._set_disconnected(f"Not connected to Music Assistant: {reason}")
        if was_connected:
            LOGGER.warning("Live capture lost its Music Assistant connection: %s", reason)
        else:
            LOGGER.debug("Live capture could not connect to Music Assistant: %s", reason)
        return 0.0 if connected_at is None else self.clock() - connected_at

    async def _refresh_player_names(
        self, client: MusicAssistantClient, init_ready: asyncio.Event
    ) -> None:
        """Take every player's name once the client has fetched the initial state."""
        await init_ready.wait()
        for player in client.players:
            self._take_name(player)

    @callback
    def _on_player_event(self, event: MassEvent) -> None:
        """Keep a renamed or newly added player's name current."""
        client = self._client
        if client is None or not event.object_id:
            return
        player = client.players.get(event.object_id)
        if player is not None:
            self._take_name(player)

    def _take_name(self, player: Any) -> None:
        """Keep a player's name - only a real one; an empty name never replaces a known one."""
        if label := _player_label(player):
            self.player_names[player.player_id] = label

    @callback
    def _on_media_item_played(self, event: MassEvent) -> None:
        """Fold one progress report in; write whatever plays it finished."""
        data = event.data
        if self._stopped or not isinstance(data, dict):
            # stopped: an event queued before the connection closed, arriving after the final
            # flush - the store may already be closing
            return
        report = PlayReport.from_event_data(data)
        if report is None:
            LOGGER.debug("Ignoring a media_item_played event that is not a usable report")
            return
        self._write(self.tracker.report(report, self.clock()))

    @callback
    def _handle_flush_interval(self, now: Any) -> None:
        """Timer: write the plays of players that have gone quiet."""
        self._write(self.tracker.flush_idle(self.clock()))

    @callback
    def _write(self, captured: list[CapturedListen]) -> None:
        """Store finished plays in the background (the event callback cannot await)."""
        if not captured:
            return
        last = captured[-1].listen
        self.status.plays_captured += len(captured)
        self.status.last_play = f"{last.artist_name} - {last.track_name}"
        self.status.last_play_at = last.played_at
        self._notify()
        task = self.entry.async_create_background_task(
            self.hass, self._store(captured), "Listening Genome: store captured plays"
        )
        self._writes.add(task)
        task.add_done_callback(self._writes.discard)

    async def _store(self, captured: list[CapturedListen]) -> None:
        try:
            added = await self.operations.record_live(captured)
        except Exception:
            LOGGER.exception("Could not store %d captured play(s)", len(captured))
            return
        LOGGER.debug("Stored %d captured play(s), %d new", len(captured), added)
        # remember who played it: a phone's or browser's player exists in Music Assistant only
        # while it is connected, so its name has to be kept now or it is gone for good
        names = {
            listen.player_id: self.player_names[listen.player_id]
            for listen in (item.listen for item in captured)
            if listen.player_id and listen.player_id in self.player_names
        }
        if names:
            try:
                await self.operations.store.remember_player_names(names)
            except Exception:
                LOGGER.debug("Could not remember player names", exc_info=True)

    @callback
    def _set_disconnected(self, reason: str) -> None:
        changed = self.status.connected or self.status.last_error != reason
        self.status.connected = False
        self.status.connected_since = None
        self.status.last_error = reason
        if changed:
            self._notify()

    @callback
    def _notify(self) -> None:
        for update_callback in list(self._listeners):
            update_callback()


_UNKNOWN_DEVICE_INFO = frozenset({"", "unknown model", "unknown manufacturer"})


def _player_label(player: Any) -> str | None:
    """
    A name for a Music Assistant player: its own, else what its device info says it is.

    Some players (a phone playing through the Music Assistant app, a browser tab) can arrive
    with an empty name; the model is better than nothing.
    """
    name = str(getattr(player, "name", "") or "").strip()
    if name:
        return name
    info = getattr(player, "device_info", None)
    parts = [str(getattr(info, attr, "") or "").strip() for attr in ("manufacturer", "model")]
    parts = [part for part in parts if part.casefold() not in _UNKNOWN_DEVICE_INFO]
    return " ".join(dict.fromkeys(parts)) or None


__all__ = ["CaptureStatus", "MusicAssistantCapture"]
