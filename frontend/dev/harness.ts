/**
 * Dev harness: mounts <listening-genome-panel> with a fake `hass` that answers the
 * integration's websocket commands from fixtures, so the panel can be built and screenshotted
 * without a Home Assistant. The fixture genome is the fork's synthetic sample - never real
 * listening data.
 *
 * URL parameters: ?view=import, ?state=empty|loading|error|enriching|unresolved,
 * ?width=... is up to the screenshot script. ?admin=0 renders as a non-admin user.
 */
import "../src/panel";
import sample from "./genome_sample.json";
import { fixtureDiscovery, fixtureImportLastfm, fixtureJobs, fixtureLive, fixturePlayers } from "./fixtures";

const params = new URLSearchParams(location.search);
const state = params.get("state") ?? "ok";
const calls: Record<string, unknown>[] = [];
(window as unknown as { __calls: unknown }).__calls = calls;

function genome() {
  const g = structuredClone(sample) as Record<string, any>;
  if (state === "empty") g.stats.total_listens = 0;
  if (state === "enriching") g.stats.artists_pending = 42;
  if (state === "unresolved") {
    g.stats.artists_pending = 0;
    g.stats.artists_failed = 3;
    g.stats.unresolved_dismissed = false;
  }
  return g;
}

const hass = {
  user: { is_admin: params.get("admin") !== "0", name: "Bob" },
  language: "en",
  async callWS(msg: Record<string, unknown>): Promise<unknown> {
    calls.push(msg);
    await new Promise((r) => setTimeout(r, 30));
    switch (msg.type) {
      case "listening_genome/get":
        if (state === "loading") return new Promise(() => undefined);
        if (state === "error") throw { code: "not_found", message: "No genome has been computed yet" };
        return genome();
      case "listening_genome/rebuild":
        return { listener: "household", listens_scanned: 1, duration_ms: 5, genome: genome() };
      case "listening_genome/jobs":
        return fixtureJobs(params.get("jobs"));
      case "listening_genome/live":
        return fixtureLive;
      case "listening_genome/discovery":
        return fixtureDiscovery(params.get("discovery"));
      case "listening_genome/players":
        return fixturePlayers;
      case "listening_genome/play":
        if (msg.song === "Missing Song")
          throw { code: "play_failed", message: "Could not resolve ['Missing Song'] to playable media item" };
        return { playing: msg.song, on: msg.entity_id };
      case "listening_genome/unresolved_artists":
        return [
          { artist_key: "a", artist_name: "Nobody Known", resolved_at: Date.now() / 1000 - 7200 },
          { artist_key: "b", artist_name: "Radiohead", resolved_at: Date.now() / 1000 - 3 * 86400 },
        ];
      case "listening_genome/import_lastfm":
        return fixtureImportLastfm(params.get("lastfm"));
      case "listening_genome/discovery_refresh":
      case "listening_genome/import_apple":
      case "listening_genome/retry_artists":
      case "listening_genome/dismiss_unresolved":
        return { job: "x", state: "running", message: "", started_at: 0, finished_at: null, progress: null };
      default:
        throw { code: "unknown_command", message: `unknown ${String(msg.type)}` };
    }
  },
  async fetchWithAuth(): Promise<Response> {
    return new Response(JSON.stringify({ file_id: "upload-1" }), { status: 200 });
  },
};

const panel = document.createElement("listening-genome-panel") as HTMLElement & Record<string, unknown>;
panel.panel = { config: { static_base: "../../custom_components/listening_genome/frontend" } };
panel.narrow = params.get("narrow") === "1";
panel.route = { prefix: "/listening-genome", path: params.get("view") === "import" ? "/import" : "" };
panel.hass = hass;
document.body.append(panel);
window.addEventListener("location-changed", () => {
  panel.route = {
    prefix: "/listening-genome",
    path: location.pathname.endsWith("/import") ? "/import" : "",
  };
});
