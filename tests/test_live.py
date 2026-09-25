"""Tests for :mod:`listening_genome.core.live`: progress reports in, one listen per play out."""

from __future__ import annotations

from typing import Any

from listening_genome.core.live import (
    IDLE_TIMEOUT_SECONDS,
    LivePlayTracker,
    PlayReport,
)

T0 = 1_790_000_000.0


def _report(**overrides: Any) -> PlayReport:
    data: dict[str, Any] = {
        "uri": "library://track/1",
        "media_type": "track",
        "name": "Bohemian Like You",
        "artist": "The Dandy Warhols",
        "artists": ["The Dandy Warhols"],
        "album": "Thirteen Tales from Urban Bohemia",
        "duration": 211,
        "seconds_played": 30,
        "fully_played": False,
        "is_playing": True,
        "player_id": "kitchen",
        "userid": "bob",
    }
    data.update(overrides)
    report = PlayReport.from_event_data(data)
    assert report is not None
    return report


def _play_through(tracker: LivePlayTracker, *, start: float, uri: str, duration: int = 211) -> list:
    """Feed the reports MA sends for one uninterrupted play; return what they finished."""
    out = []
    for elapsed in range(30, duration - 10, 30):
        out += tracker.report(_report(uri=uri, seconds_played=elapsed), start + elapsed)
    # the final report for this item arrives when the queue moves on
    out += tracker.report(
        _report(uri=uri, seconds_played=duration - 2, fully_played=True, is_playing=False),
        start + duration,
    )
    return out


def test_one_uninterrupted_play_is_one_listen_stamped_at_its_start() -> None:
    """Seven progress reports and a final one become a single listen, played_at = start."""
    tracker = LivePlayTracker()
    finished = _play_through(tracker, start=T0, uri="library://track/1")
    assert len(finished) == 1
    listen = finished[0].listen
    assert listen.played_at == int(T0)
    assert listen.artist_key == "the dandy warhols"
    assert listen.track_key == "bohemian like you"
    assert listen.source == "ma_playlog"
    assert listen.player_id == "kitchen"
    assert listen.duration_ms == 211_000
    assert listen.played_ms == 209_000
    assert listen.fully_played is True
    assert finished[0].userid == "bob"
    assert tracker.open_plays == 0


def test_skipping_to_the_next_track_closes_the_previous_play() -> None:
    """A report for a different item on the same player finishes the open play (not fully)."""
    tracker = LivePlayTracker()
    assert tracker.report(_report(seconds_played=40), T0 + 40) == []
    finished = tracker.report(_report(uri="library://track/2", seconds_played=5), T0 + 50)
    assert len(finished) == 1
    assert finished[0].listen.fully_played is False
    assert finished[0].listen.played_ms == 40_000
    assert tracker.open_plays == 1


def test_players_are_tracked_separately() -> None:
    """Two rooms playing different tracks at once do not close each other's plays."""
    tracker = LivePlayTracker()
    tracker.report(_report(player_id="kitchen", seconds_played=30), T0)
    assert tracker.report(_report(player_id="office", uri="library://track/9"), T0 + 1) == []
    assert tracker.open_plays == 2


def test_pause_and_resume_is_still_one_play() -> None:
    """Paused (not playing, not finished) then resumed: one listen, not two."""
    tracker = LivePlayTracker()
    tracker.report(_report(seconds_played=60), T0 + 60)
    assert tracker.report(_report(seconds_played=75, is_playing=False), T0 + 75) == []
    # five minutes later, playback resumes and runs to the end
    tracker.report(_report(seconds_played=90), T0 + 390)
    finished = tracker.report(
        _report(seconds_played=209, fully_played=True, is_playing=False), T0 + 510
    )
    assert len(finished) == 1
    assert finished[0].listen.played_at == int(T0)


def test_idle_player_is_closed_after_the_timeout_and_not_before() -> None:
    """Stopped half-way and never resumed: written after the idle timeout with what it had."""
    tracker = LivePlayTracker()
    tracker.report(_report(seconds_played=90, is_playing=False), T0 + 90)
    assert tracker.flush_idle(T0 + 90 + IDLE_TIMEOUT_SECONDS - 1) == []
    finished = tracker.flush_idle(T0 + 90 + IDLE_TIMEOUT_SECONDS + 1)
    assert [c.listen.played_ms for c in finished] == [90_000]


def test_resume_after_the_idle_close_does_not_count_the_track_twice() -> None:
    """A long pause was written out as a listen; resuming it later must not add another."""
    tracker = LivePlayTracker()
    tracker.report(_report(seconds_played=90, is_playing=False), T0 + 90)
    assert len(tracker.flush_idle(T0 + 90 + IDLE_TIMEOUT_SECONDS + 1)) == 1
    resumed_at = T0 + 3 * 3600
    tracker.report(_report(seconds_played=120), resumed_at)
    finished = tracker.report(
        _report(seconds_played=209, fully_played=True, is_playing=False), resumed_at + 90
    )
    assert finished == []


def test_repeat_one_counts_every_play() -> None:
    """The same track again from the top is a new play (the scrobblers' "song on loop")."""
    tracker = LivePlayTracker()
    first = _play_through(tracker, start=T0, uri="library://track/1")
    tracker.report(_report(seconds_played=30), T0 + 241)
    second = tracker.report(
        _report(seconds_played=209, fully_played=True, is_playing=False), T0 + 422
    )
    assert len(first) == 1
    assert len(second) == 1
    assert second[0].listen.played_at > first[0].listen.played_at


def test_restart_part_way_through_splits_the_play() -> None:
    """Back to the top of the same track after 2 minutes: the first two minutes are a play."""
    tracker = LivePlayTracker()
    tracker.report(_report(seconds_played=120), T0 + 120)
    finished = tracker.report(_report(seconds_played=10), T0 + 130)
    assert [c.listen.played_ms for c in finished] == [120_000]
    assert tracker.open_plays == 1


def test_non_tracks_are_ignored() -> None:
    """Radio, podcasts and audiobooks are not part of a music-taste profile."""
    tracker = LivePlayTracker()
    for media_type in ("radio", "podcast_episode", "audiobook"):
        tracker.report(
            _report(media_type=media_type, seconds_played=300, fully_played=True, is_playing=False),
            T0,
        )
    assert tracker.open_plays == 0
    assert tracker.flush_all(T0 + 10) == []


def test_flush_all_writes_open_plays_on_shutdown() -> None:
    """Home Assistant stopping mid-track still records what was heard."""
    tracker = LivePlayTracker()
    tracker.report(_report(seconds_played=100), T0 + 100)
    finished = tracker.flush_all(T0 + 110)
    assert [c.listen.played_ms for c in finished] == [100_000]
    assert tracker.open_plays == 0


def test_restart_of_home_assistant_mid_track_lands_on_the_same_start_minute() -> None:
    """
    After a restart the tracker is new, but the start it computes is the same.

    That is what lets the store's per-minute dedupe key absorb the second copy.
    """
    before = LivePlayTracker()
    before.report(_report(seconds_played=100), T0 + 100)
    first = before.flush_all(T0 + 100)
    after = LivePlayTracker()
    after.report(_report(seconds_played=160), T0 + 162)
    second = after.flush_all(T0 + 162)
    assert first[0].listen.played_at // 60 == second[0].listen.played_at // 60


def test_multi_artist_credit_keys_on_the_first_artist() -> None:
    """The artist list's first entry, as every importer keys - not MA's joined string."""
    tracker = LivePlayTracker()
    tracker.report(
        _report(artist="Artist A, Artist B", artists=["Artist A", "Artist B"], seconds_played=50),
        T0 + 50,
    )
    [captured] = tracker.flush_all(T0 + 60)
    assert captured.listen.artist_key == "artist a"
    assert captured.listen.artist_name == "Artist A"


def test_ma_unknown_duration_placeholder_is_not_stored() -> None:
    """MA reports three hours for an item of unknown length; that is not a duration."""
    report = _report(duration=3 * 3600, seconds_played=50)
    assert report.duration is None


def test_malformed_event_data_is_rejected_not_raised() -> None:
    """Another program's wire format: a bad event yields None, never an exception."""
    assert PlayReport.from_event_data({}) is None
    assert PlayReport.from_event_data({"uri": "x", "name": "y", "seconds_played": "abc"}) is None
    assert PlayReport.from_event_data({"uri": "x"}) is None


def test_under_five_seconds_is_not_a_play() -> None:
    """A report under MA's own 5-second floor never becomes a listen."""
    tracker = LivePlayTracker()
    tracker.report(_report(seconds_played=3), T0 + 3)
    assert tracker.flush_all(T0 + 4) == []


def test_a_track_played_again_after_a_short_stop_is_a_new_play() -> None:
    """Stopped at 20 s, closed idle, played in full later: two plays, not a "resume"."""
    tracker = LivePlayTracker()
    tracker.report(_report(seconds_played=20, is_playing=False), T0 + 20)
    assert len(tracker.flush_idle(T0 + 20 + IDLE_TIMEOUT_SECONDS + 1)) == 1
    later = T0 + 2 * 3600
    tracker.report(_report(seconds_played=30), later + 30)
    finished = tracker.report(
        _report(seconds_played=209, fully_played=True, is_playing=False), later + 211
    )
    assert len(finished) == 1


def test_a_replay_from_the_top_after_an_idle_close_is_a_new_play() -> None:
    """Paused at 150 s and closed idle; the same track started over is not a resume."""
    tracker = LivePlayTracker()
    tracker.report(_report(seconds_played=150, is_playing=False), T0 + 150)
    tracker.flush_idle(T0 + 150 + IDLE_TIMEOUT_SECONDS + 1)
    later = T0 + 2 * 3600
    tracker.report(_report(seconds_played=30), later + 30)
    finished = tracker.flush_all(later + 60)
    assert len(finished) == 1


def test_repeat_one_of_a_short_track_counts_every_loop() -> None:
    """
    A 100-second track on repeat-one: ticks 30, 60, 90, 30, 60, 90, ... with no final report.

    MA sends no "finished" report between loops, so the drop back to 30 s is the only sign.
    """
    tracker = LivePlayTracker()
    finished = []
    now = T0
    for _loop in range(3):
        for elapsed in (30, 60, 90):
            now += 30
            finished += tracker.report(_report(seconds_played=elapsed, duration=100), now)
        now += 10
    finished += tracker.flush_all(now)
    assert len(finished) == 3
