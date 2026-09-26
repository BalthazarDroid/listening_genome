/**
 * Every call the panel makes: Home Assistant websocket commands, via the `hass` object the
 * panel is handed. No token, no URL, no CORS - Home Assistant authenticates the connection.
 */
import type {
  DiscoveryResult,
  FailedArtist,
  GenomeJobs,
  GenomeRebuildResult,
  GenomeResult,
  LiveStatus,
  SpeakerList,
} from "./types";

/** The slice of Home Assistant's frontend `hass` object the panel uses. */
export interface Hass {
  callWS<T>(msg: Record<string, unknown>): Promise<T>;
  fetchWithAuth(path: string, init?: RequestInit): Promise<Response>;
  user?: { is_admin: boolean; name?: string };
  language?: string;
}

const P = "listening_genome";

export class GenomeApi {
  constructor(private readonly hass: Hass) {}

  getGenome = () => this.hass.callWS<GenomeResult>({ type: `${P}/get` });
  rebuild = (enrich = true) =>
    this.hass.callWS<GenomeRebuildResult>({ type: `${P}/rebuild`, enrich });
  jobs = () => this.hass.callWS<GenomeJobs>({ type: `${P}/jobs` });
  live = () => this.hass.callWS<LiveStatus>({ type: `${P}/live` });
  unresolvedArtists = (limit = 100) =>
    this.hass.callWS<FailedArtist[]>({ type: `${P}/unresolved_artists`, limit });
  retryArtists = () => this.hass.callWS<number>({ type: `${P}/retry_artists` });
  dismissUnresolved = () => this.hass.callWS<boolean>({ type: `${P}/dismiss_unresolved` });
  discovery = () => this.hass.callWS<DiscoveryResult>({ type: `${P}/discovery` });
  discoveryRefresh = () => this.hass.callWS<unknown>({ type: `${P}/discovery_refresh` });
  players = () => this.hass.callWS<SpeakerList>({ type: `${P}/players` });
  play = (entityId: string, artist: string, song: string) =>
    this.hass.callWS<{ playing: string; on: string }>({
      type: `${P}/play`,
      entity_id: entityId,
      artist,
      song,
    });
  importLastfm = (maxPages = 0) =>
    this.hass.callWS<unknown>({ type: `${P}/import_lastfm`, max_pages: maxPages });

  /**
   * Upload an Apple Music export through Home Assistant's own file-upload endpoint, then ask
   * the integration to import it. Returns once the import has STARTED; its outcome is the
   * `apple_import` job.
   */
  async importApple(file: File): Promise<void> {
    const form = new FormData();
    form.append("file", file);
    const response = await this.hass.fetchWithAuth("/api/file_upload", {
      method: "POST",
      body: form,
    });
    if (!response.ok) {
      throw new Error(
        response.status === 413
          ? "The file is larger than Home Assistant accepts (100 MB)."
          : `Upload failed (HTTP ${response.status}).`,
      );
    }
    const { file_id: fileId } = (await response.json()) as { file_id: string };
    await this.hass.callWS({ type: `${P}/import_apple`, file_id: fileId, filename: file.name });
  }
}

/** The message of a failed websocket call (Home Assistant rejects with `{code, message}`). */
export function errorMessage(err: unknown): string {
  if (err && typeof err === "object" && "message" in err) {
    return String((err as { message: unknown }).message);
  }
  return String(err);
}
