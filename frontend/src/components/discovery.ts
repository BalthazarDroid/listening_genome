/**
 * <lg-discovery>: artists worth trying next - Last.fm suggestions not in the library, and the
 * household's own cold corners - ported from the fork's GenomeDiscovery.vue.
 *
 * Added for Home Assistant (Bob, 2026-09-25): every row names its one song ("Try: ...") and a
 * play button plays JUST that song on the speaker chosen in the card's single speaker menu.
 *
 * `listening_genome/discovery` is a pure database read, so loading never triggers network
 * work; only the admin's refresh button starts a pass, after which the card polls the
 * `discovery` job every 2 s and re-reads once it has finished.
 */
import { LitElement, css, html, nothing } from "lit";
import { errorMessage, type GenomeApi } from "../api";
import { t } from "../i18n";
import { iconLoader, iconPlay, iconRefresh } from "../icons";
import { genomeBase, genomeTokens } from "../styles";
import type { DiscoveryResult, GenomeJobs, SpeakerList } from "../types";
import { defaultSpeaker, markFor, markLine, matchPercent, rowKey } from "./discovery-logic";

const POLL_MS = 2000;
const CONFIRM_MS = 4000;
const SPEAKER_KEY = "listening-genome.speaker";

type RowState =
  | { status: "starting" }
  | { status: "playing"; speaker: string }
  | { status: "error"; message: string };

/** The speaker picked this session: module memory, mirrored to sessionStorage for reloads. */
let rememberedSpeaker: string | null = null;
function readRemembered(): string | null {
  if (rememberedSpeaker) return rememberedSpeaker;
  try {
    return sessionStorage.getItem(SPEAKER_KEY);
  } catch {
    return null;
  }
}
function remember(entityId: string): void {
  rememberedSpeaker = entityId;
  try {
    sessionStorage.setItem(SPEAKER_KEY, entityId);
  } catch {
    /* private mode: module memory still holds it */
  }
}

export class GenomeDiscovery extends LitElement {
  static properties = {
    api: { attribute: false },
    isAdmin: { type: Boolean },
    _data: { state: true },
    _loadError: { state: true },
    _refreshing: { state: true },
    _refreshError: { state: true },
    _speakers: { state: true },
    _speaker: { state: true },
    _rows: { state: true },
  };

  api?: GenomeApi;
  isAdmin = false;
  private _data: DiscoveryResult | null = null;
  private _loadError = false;
  private _refreshing = false;
  private _refreshError = "";
  private _speakers: SpeakerList | null = null;
  private _speaker: string | null = null;
  private _rows: Record<string, RowState> = {};
  private _poll?: ReturnType<typeof setTimeout>;
  private _confirmTimers = new Map<string, ReturnType<typeof setTimeout>>();
  private _loadedFor?: GenomeApi;

  static styles = [
    genomeTokens,
    genomeBase,
    css`
      :host {
        display: block;
        min-width: 0;
      }
      .panel {
        gap: 14px;
      }
      .header-actions {
        display: flex;
        align-items: center;
        gap: 4px;
        margin: -6px -6px 0 0;
      }
      .lead,
      .empty {
        font-size: 11.5px;
        line-height: 1.5;
        color: hsl(215 8% 50%);
      }
      .empty {
        color: hsl(215 8% 52%);
      }
      .speaker-row {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
      }
      .speaker-row label {
        flex: none;
      }
      .speaker-row select {
        flex: 1 1 auto;
        min-width: 0;
        max-width: 100%;
        font-size: 12.5px;
      }
      section {
        display: flex;
        flex-direction: column;
        gap: 7px;
      }
      .label {
        margin: 0;
        padding-bottom: 5px;
        border-bottom: 1px solid var(--genome-panel-border);
      }
      .link {
        color: var(--genome-accent);
        text-decoration: none;
        border-bottom: 1px solid hsl(190 85% 62% / 0.35);
      }
      .link:hover {
        border-bottom-color: var(--genome-accent);
      }
      .list {
        display: flex;
        flex-direction: column;
        gap: 2px;
        /* long enough to be worth scrolling, short enough not to outgrow the heatmap */
        max-height: 300px;
        overflow-y: auto;
      }
      .strand {
        display: flex;
        align-items: center;
        gap: 9px;
        padding: 5px 4px 5px 6px;
        border-radius: 6px;
        transition: background-color 120ms ease;
      }
      .strand:hover {
        background: hsl(205 55% 65% / 0.05);
      }
      .mark {
        width: 11px;
        height: 11px;
        flex: 0 0 auto;
        border-radius: 50%;
      }
      .body {
        display: flex;
        flex-direction: column;
        gap: 1px;
        min-width: 0;
        flex: 1 1 auto;
      }
      .name,
      .meta,
      .song,
      .feedback {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .name {
        font-size: 12.5px;
        color: hsl(210 14% 84%);
      }
      .meta {
        font: 600 9px/1.3 var(--genome-mono);
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: hsl(215 8% 50%);
      }
      .song {
        font-size: 11.5px;
        color: hsl(210 10% 66%);
      }
      .feedback {
        font-size: 11px;
        color: var(--genome-accent);
      }
      .feedback.error {
        color: hsl(0 80% 72%);
        white-space: normal;
      }
      /* the match is a bar, not a number: Last.fm's figure is ordinal in practice */
      .score {
        flex: 0 0 34px;
        height: 3px;
        border-radius: 2px;
        background: hsl(215 40% 60% / 0.12);
        overflow: hidden;
      }
      .bar {
        display: block;
        height: 100%;
        border-radius: 2px;
      }
      .play {
        flex: none;
        width: 30px;
        height: 30px;
        border-color: hsl(190 85% 62% / 0.25);
        color: var(--genome-accent);
      }
      .play .icon {
        width: 13px;
        height: 13px;
      }
      .play-spacer {
        flex: none;
        width: 30px;
      }
      .empty.error {
        color: hsl(0 80% 72%);
      }
    `,
  ];

  protected updated(changed: Map<string, unknown>): void {
    if (changed.has("api") && this.api && this._loadedFor !== this.api) {
      this._loadedFor = this.api;
      void this._load();
      void this._loadSpeakers();
    }
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    clearTimeout(this._poll);
    this._poll = undefined;
    for (const timer of this._confirmTimers.values()) clearTimeout(timer);
    this._confirmTimers.clear();
  }

  connectedCallback(): void {
    super.connectedCallback();
    // re-attached while a refresh was in flight: pick the poll back up
    if (this._refreshing && !this._poll) this._schedulePoll();
  }

  private async _load(): Promise<void> {
    if (!this.api) return;
    try {
      this._data = await this.api.discovery();
      this._loadError = false;
    } catch {
      this._loadError = true;
    }
  }

  private async _loadSpeakers(): Promise<void> {
    if (!this.api) return;
    try {
      const list = await this.api.players();
      this._speakers = list;
      this._speaker = defaultSpeaker(list, readRemembered());
    } catch {
      this._speakers = { players: [], last_used: null };
      this._speaker = null;
    }
  }

  private async _refresh(): Promise<void> {
    if (!this.api || this._refreshing) return;
    this._refreshing = true;
    this._refreshError = "";
    try {
      await this.api.discoveryRefresh();
    } catch (err) {
      // already_running is fine: wait for that pass instead
      if ((err as { code?: string })?.code !== "already_running") {
        this._refreshError = errorMessage(err);
        this._refreshing = false;
        return;
      }
    }
    this._schedulePoll();
  }

  private _schedulePoll(): void {
    clearTimeout(this._poll);
    this._poll = setTimeout(() => void this._pollJobs(), POLL_MS);
  }

  private async _pollJobs(): Promise<void> {
    this._poll = undefined;
    if (!this.api || !this.isConnected) return;
    let jobs: GenomeJobs | null = null;
    try {
      jobs = await this.api.jobs();
    } catch {
      jobs = null; // transient: try again next tick
    }
    if (jobs && jobs.discovery?.state !== "running") {
      this._refreshing = false;
      if (jobs.discovery?.state === "error") this._refreshError = jobs.discovery.message;
      await this._load();
      return;
    }
    this._schedulePoll();
  }

  private _speakerName(entityId: string | null): string {
    return this._speakers?.players.find((p) => p.entity_id === entityId)?.name ?? entityId ?? "";
  }

  private _chooseSpeaker(e: Event): void {
    const value = (e.target as HTMLSelectElement).value;
    this._speaker = value || null;
    if (value) remember(value);
  }

  private _setRow(key: string, state: RowState | null): void {
    const rows = { ...this._rows };
    if (state) rows[key] = state;
    else delete rows[key];
    this._rows = rows;
  }

  private async _play(key: string, artist: string, song: string): Promise<void> {
    const entityId = this._speaker;
    if (!this.api || !entityId) return;
    const speaker = this._speakerName(entityId);
    clearTimeout(this._confirmTimers.get(key));
    this._setRow(key, { status: "starting" });
    try {
      await this.api.play(entityId, artist, song);
      this._setRow(key, { status: "playing", speaker });
      this._confirmTimers.set(
        key,
        setTimeout(() => {
          this._confirmTimers.delete(key);
          if (this._rows[key]?.status === "playing") this._setRow(key, null);
        }, CONFIRM_MS),
      );
    } catch (err) {
      this._setRow(key, { status: "error", message: errorMessage(err) });
    }
  }

  render() {
    return html`<div class="panel">
      <div class="panel-header">
        <h2 class="panel-title">${t("discovery.title")}</h2>
        ${this.isAdmin
          ? html`<div class="header-actions">
              <button
                class="icon-btn"
                ?disabled=${this._refreshing}
                aria-label=${t("discovery.refresh")}
                title=${t("discovery.refresh")}
                @click=${this._refresh}
              >
                ${iconRefresh(this._refreshing ? "icon spin" : "icon")}
              </button>
            </div>`
          : nothing}
      </div>
      <p class="lead">${t("discovery.lead")}</p>
      ${this._speakerMenu()}
      ${this._refreshing
        ? html`<p class="empty" role="status">${t("panel.discovery.refreshing")}</p>`
        : nothing}
      ${this._refreshError
        ? html`<p class="empty error" role="alert">
            ${t("panel.discovery.refresh_failed", { error: this._refreshError })}
          </p>`
        : nothing}
      ${this._suggested()} ${this._cold()}
      ${this._loadError ? html`<p class="empty error">${t("discovery.error")}</p>` : nothing}
    </div>`;
  }

  private _speakerMenu() {
    const list = this._speakers;
    if (!list) return nothing;
    const id = "lg-speaker";
    return html`<div class="speaker-row">
      <label class="code" for=${id}>${t("panel.discovery.speaker_label")}</label>
      <select id=${id} .value=${this._speaker ?? ""} @change=${this._chooseSpeaker}
        ?disabled=${!list.players.some((p) => p.available)}>
        ${list.players.length === 0
          ? html`<option value="">${t("panel.discovery.no_speakers")}</option>`
          : list.players.map(
              (p) => html`<option
                value=${p.entity_id}
                ?disabled=${!p.available}
                ?selected=${p.entity_id === this._speaker}
              >
                ${p.available ? p.name : t("panel.discovery.speaker_unavailable", { name: p.name })}
              </option>`,
            )}
      </select>
    </div>`;
  }

  private _suggested() {
    const data = this._data;
    let body;
    if (!data) body = nothing;
    else if (data.suggested_state === "unavailable")
      body = html`<p class="empty">${t("panel.discovery.no_lastfm_where")}</p>`;
    else if (data.suggested_state === "pending")
      body = html`<p class="empty">${t("discovery.pending")}</p>`;
    else if (data.suggested.length === 0)
      body = html`<p class="empty">${t("discovery.no_suggestions")}</p>`;
    else
      body = html`<ul class="list">
        ${data.suggested.map((a) =>
          this._row(
            rowKey("suggested", a.artist_name, a.song ?? ""),
            a.artist_name,
            a.song ?? null,
            a.genre_key,
            t("discovery.because", { seed: a.seed_artist }),
            html`<span class="score" title=${t("discovery.match_title")}>
              <span
                class="bar"
                style="width:${matchPercent(a.match)}%;background:${markLine(a.genre_key)}"
              ></span>
            </span>`,
          ),
        )}
      </ul>`;
    return html`<section>
      <h3 class="code label">${t("discovery.suggested_heading")}</h3>
      ${body}
    </section>`;
  }

  private _cold() {
    const data = this._data;
    let body;
    if (!data) body = nothing;
    else if (data.in_library.length === 0)
      body = html`<p class="empty">${t("discovery.no_cold")}</p>`;
    else
      body = html`<ul class="list">
        ${data.in_library.map((a) => {
          const plays =
            a.plays === 0 ? t("discovery.never_played") : t("discovery.n_plays", { plays: a.plays });
          return this._row(
            rowKey("cold", a.artist_name, a.song ?? ""),
            a.artist_name,
            a.song ?? null,
            a.genre_key,
            a.genre_label ? `${plays} · ${a.genre_label}` : plays,
            nothing,
          );
        })}
      </ul>`;
    return html`<section>
      <h3 class="code label">${t("discovery.cold_heading")}</h3>
      ${body}
    </section>`;
  }

  private _row(
    key: string,
    artist: string,
    song: string | null,
    genreKey: string | null,
    meta: string,
    score: unknown,
  ) {
    const state = this._rows[key];
    return html`<li class="strand">
      <span class="mark" style="background:${markFor(genreKey)}" aria-hidden="true"></span>
      <span class="body">
        <span class="name">${artist}</span>
        <span class="meta">${meta}</span>
        ${song ? html`<span class="song">${t("panel.discovery.try", { song })}</span>` : nothing}
        <span role="status" aria-live="polite">${this._feedback(state)}</span>
      </span>
      ${score} ${song ? this._playButton(key, artist, song, state) : html`<span class="play-spacer"></span>`}
    </li>`;
  }

  private _feedback(state: RowState | undefined) {
    if (!state) return nothing;
    if (state.status === "starting")
      return html`<span class="feedback">${t("panel.discovery.starting")}</span>`;
    if (state.status === "playing")
      return html`<span class="feedback"
        >${t("panel.discovery.playing_on", { speaker: state.speaker })}</span
      >`;
    return html`<span class="feedback error">${state.message}</span>`;
  }

  private _playButton(key: string, artist: string, song: string, state: RowState | undefined) {
    const speaker = this._speaker;
    const busy = state?.status === "starting";
    const label = speaker
      ? t("panel.discovery.play_aria", { song, artist, speaker: this._speakerName(speaker) })
      : t("panel.discovery.no_speaker_title");
    return html`<button
      class="icon-btn play"
      aria-label=${label}
      title=${label}
      aria-busy=${busy ? "true" : "false"}
      ?disabled=${!speaker || busy}
      @click=${() => this._play(key, artist, song)}
    >
      ${busy ? iconLoader() : iconPlay()}
    </button>`;
  }
}

if (!customElements.get("lg-discovery")) customElements.define("lg-discovery", GenomeDiscovery);
