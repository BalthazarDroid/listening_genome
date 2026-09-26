/** Fixture answers for the dev harness (synthetic: never real listening data). */
const now = () => Math.round(Date.now() / 1000);

export const fixtureLive = {
  connected: true,
  server_version: "2.9.0",
  last_error: null,
  plays_captured: 12,
  last_play: "Tame Impala - Let It Happen",
  last_play_at: now() - 600,
  connected_since: now() - 86400,
};

export const fixturePlayers = {
  players: [
    { entity_id: "media_player.kitchen", name: "Kitchen speaker", available: true },
    { entity_id: "media_player.office", name: "Office speaker", available: true },
    { entity_id: "media_player.porch", name: "Back porch", available: false },
  ],
  last_used: "media_player.office",
};

export function fixtureDiscovery(variant: string | null) {
  const suggested = [
    ["Tess Parks", "The Brian Jonestown Massacre", "psychedelic", 1, "Somedays"],
    ["Psychic Ills", "The Brian Jonestown Massacre", "psychedelic", 0.83, "Mind Daze"],
    ["Eartheater", "Grimes", "ambient", 0.71, "Supersoaker"],
    ["Pale Saints", "Mazzy Star", "psychedelic", 0.27, "Kinky Love"],
    ["Philip Selway", "Radiohead", "ambient", 0.22, "By Some Miracle"],
    ["Missing Band", "Warpaint", "psychedelic", 0.2, "Missing Song"],
    ["No Song Band", "Metric", "ambient", 0.18, null],
  ].map(([artist_name, seed_artist, genre, match, song]) => ({
    artist_name,
    mbid: null,
    seed_artist,
    genre_key: genre,
    genre_label: genre,
    match,
    song,
  }));
  const in_library = [
    { artist_key: "tame impala", artist_name: "Tame Impala", plays: 0, genre_key: "psychedelic", genre_label: "psychedelic", song: "Let It Happen" },
    { artist_key: "slowdive", artist_name: "Slowdive", plays: 2, genre_key: "ambient", genre_label: "ambient", song: "Alison" },
  ];
  if (variant === "unavailable")
    return { in_library, suggested: [], suggested_state: "unavailable", generated_at: now() - 3600 };
  if (variant === "pending")
    return { in_library: [], suggested: [], suggested_state: "pending", generated_at: null };
  return { in_library, suggested, suggested_state: "ready", generated_at: now() - 3600 };
}

export function fixtureJobs(variant: string | null) {
  const job = (name: string, state: string, message: string, progress: number | null = null) => ({
    job: name,
    state,
    message,
    started_at: now() - 300,
    finished_at: state === "running" ? null : now() - 60,
    progress,
  });
  const running = variant === "running";
  return {
    rebuild: job("rebuild", "ok", "Rebuilt from 198,865 stored listens in 6850 ms"),
    enrichment: job("enrichment", running ? "running" : "ok", running ? "MusicBrainz: 120 of 400 looked up" : "MusicBrainz: 3 resolved", running ? 30 : 100),
    lastfm_import: job("lastfm_import", running ? "running" : "ok", running ? "Importing scrobbles for testuser..." : "Last.fm import finished: 349 imported, 0 skipped, 0 duplicate (of 349 rows read)"),
    apple_import: variant === "error"
      ? job("apple_import", "error", "Apple Music import of export.csv failed: the file has no Track Description column")
      : job("apple_import", "idle", ""),
    duplicates: job("duplicates", "ok", "Removed 22664 Last.fm plays already recorded by another source"),
    discovery: job("discovery", "ok", "Discovery finished: 30 artists suggested from 8 of your favourites (30 with a song)"),
  };
}

/** `listening_genome/import_lastfm`: ?lastfm=unset answers as the backend does with no account. */
export function fixtureImportLastfm(variant: string | null) {
  if (variant === "unset")
    throw {
      code: "not_configured",
      message: "Last.fm is not set up: add the username and API key in the integration's settings",
    };
  return { job: "lastfm_import", state: "running", message: "", started_at: now(), finished_at: null, progress: null };
}
