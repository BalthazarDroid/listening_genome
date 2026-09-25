"""
Turn Music Assistant's playback progress reports into one listen per play.

Music Assistant emits ``media_item_played`` (a ``MediaItemPlaybackProgressReport``) for every
queue: every 30 seconds while something plays, on pause and stop, and once more for the previous
item when the queue moves on. It is the event MA's own Last.fm and ListenBrainz scrobblers are
built on, it exists in every MA server Home Assistant supports, and - unlike the fork's
``playlog_updated`` - it names the player and carries the artist, title, album and duration, so
nothing has to be looked up afterwards.

A stream of progress reports is not a list of plays, though. :class:`LivePlayTracker` keeps one
open *session* per player and closes it into a single :class:`~.models.Listen` when:

* a report for a **different item** arrives on that player (the queue moved on);
* a report says the item is **fully played and no longer playing** (it ended);
* the same item **starts again from the top** (repeat-one, or played again);
* nothing has been heard from the player for :data:`IDLE_TIMEOUT_SECONDS` (stopped for good,
  or Home Assistant lost the connection) - see :meth:`LivePlayTracker.flush_idle`;
* the integration unloads or Home Assistant stops - :meth:`LivePlayTracker.flush_all`.

Each listen is stamped with the time the play STARTED (first report time minus the seconds
already played). Every other source is stamped that way - Last.fm with the scrobble start, Apple
with the hour - and it makes the result stable: a restart of Home Assistant mid-track re-opens
the session at the same start minute, so the store's per-minute ``dedupe_key`` absorbs the
second copy instead of counting the track twice.

No Home Assistant or Music Assistant imports: reports arrive as :class:`PlayReport`, built by
the caller from the event's plain ``dict``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..compat import create_safe_string, parse_title_and_version
from .constants import SOURCE_MA_PLAYLOG
from .models import Listen

if TYPE_CHECKING:
    from collections.abc import Mapping

#: a player unheard from this long has its open play closed with what it had so far
IDLE_TIMEOUT_SECONDS = 30 * 60

#: a paused play resumed within this long after being closed idle is the SAME play, not a new one
CONTINUATION_WINDOW_SECONDS = 6 * 3600

#: the same item reporting fewer seconds than this, after having reported more, has restarted...
RESTART_MAX_SECONDS = 60
#: ...provided it went back by at least this much (progress ticks are 30 s apart, so a
#: 100-second track on repeat-one goes 30, 60, 90, 30: a drop of 60)
RESTART_MIN_DROP_SECONDS = 25

#: a play closed idle this far into the track or further can be RESUMED; closed earlier, the
#: same track starting again is a new play (its first tick, at ~30 s, cannot tell them apart)
RESUMABLE_AFTER_SECONDS = 60
#: a resume picks up where the play was paused: its first tick is at most this far past it
RESUME_MAX_ADVANCE_SECONDS = 40

#: MA itself drops reports under 5 s; anything that slips through is not a play
MIN_SECONDS_PLAYED = 5

#: MA reports this (three hours) as the duration of an item whose length it does not know
_MA_UNKNOWN_DURATION_SECONDS = 3 * 3600

_TRACK = "track"


@dataclass(frozen=True, slots=True)
class PlayReport:
    """The fields of MA's ``MediaItemPlaybackProgressReport`` a listen needs."""

    uri: str
    media_type: str
    name: str
    seconds_played: int
    fully_played: bool
    is_playing: bool
    duration: int | None = None
    artist: str | None = None
    artists: tuple[str, ...] = ()
    album: str | None = None
    version: str | None = None
    player_id: str | None = None
    userid: str | None = None

    @classmethod
    def from_event_data(cls, data: Mapping[str, Any]) -> PlayReport | None:
        """
        Build a report from a ``media_item_played`` event's ``data`` dict, or ``None``.

        ``None`` for anything that is not a usable report: a missing ``uri`` or ``name``,
        non-numeric progress. Every field is read defensively - this is another program's
        wire format, and one malformed event must not take the capture down.
        """
        uri = data.get("uri")
        name = data.get("name")
        if not isinstance(uri, str) or not uri or not isinstance(name, str) or not name:
            return None
        try:
            seconds_played = int(data.get("seconds_played") or 0)
            duration_raw = data.get("duration")
            duration = int(duration_raw) if duration_raw else None
            if duration is not None and duration >= _MA_UNKNOWN_DURATION_SECONDS:
                duration = None
        except TypeError, ValueError:
            return None
        raw_artists = data.get("artists") or ()
        artists = tuple(a for a in raw_artists if isinstance(a, str) and a)
        return cls(
            uri=uri,
            media_type=str(data.get("media_type") or ""),
            name=name,
            seconds_played=seconds_played,
            fully_played=bool(data.get("fully_played")),
            is_playing=bool(data.get("is_playing")),
            duration=duration,
            artist=data.get("artist") if isinstance(data.get("artist"), str) else None,
            artists=artists,
            album=data.get("album") if isinstance(data.get("album"), str) else None,
            version=data.get("version") if isinstance(data.get("version"), str) else None,
            player_id=data.get("player_id") if isinstance(data.get("player_id"), str) else None,
            userid=data.get("userid") if isinstance(data.get("userid"), str) else None,
        )

    @property
    def primary_artist(self) -> str:
        """The first credited artist (as every importer keys on), else the joined string."""
        if self.artists:
            return self.artists[0]
        return self.artist or ""


@dataclass(slots=True)
class _Session:
    """One play in progress on one player."""

    report: PlayReport
    started_at: int
    last_heard: float
    seconds_played: int
    fully_played: bool
    #: this play resumes one already written (closed idle while paused), so it writes nothing
    continuation: bool = False


@dataclass(frozen=True, slots=True)
class CapturedListen:
    """A finished play: the listen to store, and the MA user it belongs to."""

    listen: Listen
    userid: str | None


@dataclass(slots=True)
class _Closed:
    """The last play closed on a player, to recognise a resume of it."""

    uri: str
    seconds_played: int
    closed_at: float


@dataclass(slots=True)
class LivePlayTracker:
    """Fold MA progress reports into listens, one open play per player."""

    idle_timeout: float = IDLE_TIMEOUT_SECONDS
    _sessions: dict[str, _Session] = field(default_factory=dict)
    _closed: dict[str, _Closed] = field(default_factory=dict)

    @property
    def open_plays(self) -> int:
        """How many players have a play in progress."""
        return len(self._sessions)

    def report(self, report: PlayReport, now: float) -> list[CapturedListen]:
        """
        Take one progress report; return whatever plays it finished (usually none).

        :param report: The report.
        :param now: The time it arrived (seconds since the epoch).
        """
        if report.media_type != _TRACK:
            # radio, podcasts and audiobooks are not part of a music-taste profile
            return []
        player = report.player_id or ""
        finished: list[CapturedListen] = []
        session = self._sessions.get(player)
        if session is not None and (
            session.report.uri != report.uri or self._restarted(session, report)
        ):
            finished.extend(self._close(player, now))
            session = None
        if session is None:
            session = self._open(player, report, now)
        session.report = report
        session.last_heard = now
        session.seconds_played = max(session.seconds_played, report.seconds_played)
        session.fully_played = session.fully_played or report.fully_played
        if report.fully_played and not report.is_playing:
            finished.extend(self._close(player, now))
        return finished

    def flush_idle(self, now: float) -> list[CapturedListen]:
        """Close every play whose player has been silent for longer than the idle timeout."""
        finished: list[CapturedListen] = []
        for player in [
            p for p, s in self._sessions.items() if now - s.last_heard > self.idle_timeout
        ]:
            finished.extend(self._close(player, now, resumable=True))
        return finished

    def flush_all(self, now: float) -> list[CapturedListen]:
        """Close every open play (shutdown): what was heard so far is still a listen."""
        finished: list[CapturedListen] = []
        for player in list(self._sessions):
            finished.extend(self._close(player, now))
        return finished

    @staticmethod
    def _restarted(session: _Session, report: PlayReport) -> bool:
        """The same item, back near the top after having played further: a new play."""
        return (
            report.seconds_played < RESTART_MAX_SECONDS
            and report.seconds_played + RESTART_MIN_DROP_SECONDS < session.seconds_played
        )

    def _open(self, player: str, report: PlayReport, now: float) -> _Session:
        session = _Session(
            report=report,
            started_at=int(now) - report.seconds_played,
            last_heard=now,
            seconds_played=report.seconds_played,
            fully_played=False,
        )
        closed = self._closed.pop(player, None)
        if (
            closed is not None
            and closed.uri == report.uri
            and now - closed.closed_at <= CONTINUATION_WINDOW_SECONDS
            and closed.seconds_played
            <= report.seconds_played
            <= closed.seconds_played + RESUME_MAX_ADVANCE_SECONDS
        ):
            # resumed after a long pause that the idle timeout already closed: the listen for
            # this play exists; writing another would count the track twice
            session.continuation = True
        self._sessions[player] = session
        return session

    def _close(self, player: str, now: float, *, resumable: bool = False) -> list[CapturedListen]:
        """
        Close a player's open play into a listen.

        :param resumable: Closed by the idle timeout, not by the play ending: remember it, so
            the same play resumed later is recognised (only when it was well under way and
            not finished - see :data:`RESUMABLE_AFTER_SECONDS`).
        """
        session = self._sessions.pop(player)
        if (
            resumable
            and not session.fully_played
            and session.seconds_played >= RESUMABLE_AFTER_SECONDS
        ):
            self._closed[player] = _Closed(
                uri=session.report.uri, seconds_played=session.seconds_played, closed_at=now
            )
        else:
            self._closed.pop(player, None)
        if session.continuation or session.seconds_played < MIN_SECONDS_PLAYED:
            return []
        listen = _to_listen(session)
        return [] if listen is None else [CapturedListen(listen, session.report.userid)]


def _to_listen(session: _Session) -> Listen | None:
    """Build the stored listen for a finished play, keyed exactly as the importers key."""
    report = session.report
    artist_name = report.primary_artist
    title, _version = parse_title_and_version(report.name, strip_for_search=True)
    artist_key = create_safe_string(artist_name) if artist_name else ""
    track_key = create_safe_string(title)
    if not artist_key or not track_key:
        return None
    return Listen(
        played_at=session.started_at,
        artist_key=artist_key,
        artist_name=artist_name,
        track_key=track_key,
        track_name=report.name,
        album_name=report.album,
        source=SOURCE_MA_PLAYLOG,
        player_id=report.player_id,
        duration_ms=report.duration * 1000 if report.duration else None,
        played_ms=session.seconds_played * 1000,
        fully_played=session.fully_played,
        confidence=1.0,
    )


__all__ = [
    "IDLE_TIMEOUT_SECONDS",
    "CapturedListen",
    "LivePlayTracker",
    "PlayReport",
]
