/**
 * <lg-import-view>: the import page, ported from the fork's GenomeSettings.vue and adapted to
 * the Home Assistant backend.
 *
 * - Apple Music: a file picker; the file goes through Home Assistant's own upload endpoint and
 *   `listening_genome/import_apple` (GenomeApi.importApple), which returns once it has STARTED.
 * - Last.fm: "Import now". The account lives in the integration's options flow, not here; when
 *   it is missing the backend answers `not_configured` and the card says where to set it.
 * - Status: EVERY job from `listening_genome/jobs`, polled every 2 s while any is running, and
 *   the Music Assistant live-capture line from `listening_genome/live`.
 *
 * Everything worth showing about a job lives on the server, so leaving and reopening the page
 * loses nothing. Non-admins see the status but not the import buttons.
 */
import { LitElement, css, html, nothing } from "lit";
import { errorMessage, type GenomeApi } from "../api";
import { t } from "../i18n";
import { iconBack, iconLoader, iconUpload } from "../icons";
import { genomeBase, genomeTokens } from "../styles";
import type { GenomeJob, GenomeJobs, LiveStatus } from "../types";
import { anyRunning, jobDetail, jobLabel, orderedJobs, relativeTime, stateLabel } from "./job-format";

const POLL_MS = 2000;
// only redraws "4 minutes ago"; nothing is fetched on this tick
const CLOCK_MS = 30_000;

type Note = { kind: "info" | "error"; text: string; hint?: string } | null;

export class GenomeImportView extends LitElement {
  static properties = {
    api: { attribute: false },
    isAdmin: { type: Boolean },
    narrow: { type: Boolean },
    _jobs: { state: true },
    _jobsError: { state: true },
    _live: { state: true },
    _liveError: { state: true },
    _now: { state: true },
    _lastfmBusy: { state: true },
    _lastfmNote: { state: true },
    _lastfmUnset: { state: true },
    _uploading: { state: true },
    _appleFile: { state: true },
    _appleNote: { state: true },
  };

  api?: GenomeApi;
  isAdmin = false;
  narrow = false;
  private _jobs: GenomeJobs | null = null;
  private _jobsError = "";
  private _live: LiveStatus | null = null;
  private _liveError = "";
  private _now = Math.floor(Date.now() / 1000);
  private _lastfmBusy = false;
  private _lastfmNote: Note = null;
  /** from discovery's `suggested_state`: known before anyone presses the button */
  private _lastfmUnset = false;
  private _uploading = false;
  private _appleFile = "";
  private _appleNote: Note = null;
  private _poll?: ReturnType<typeof setTimeout>;
  private _clock?: ReturnType<typeof setInterval>;
  private _loadedFor?: GenomeApi;

  static styles = [
    genomeTokens,
    genomeBase,
    css`
      :host {
        display: block;
      }
      .page {
        max-width: 1000px;
        margin: 0 auto;
        padding: 24px 24px 48px;
        display: flex;
        flex-direction: column;
        gap: 20px;
      }
      :host([narrow]) .page {
        padding: 64px 16px 32px;
      }
      header {
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      .back {
        align-self: flex-start;
      }
      h1 {
        margin: 0;
        font-size: 20px;
      }
      .subtitle {
        font-size: 13px;
        color: var(--genome-muted);
      }
      .cards {
        display: grid;
        gap: 20px;
      }
      @media (min-width: 820px) {
        .cards {
          grid-template-columns: 1fr 1fr;
        }
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 10px;
      }
      .file-name {
        font-size: 12px;
        color: var(--genome-muted);
        overflow-wrap: anywhere;
      }
      .note {
        font-size: 12.5px;
        line-height: 1.5;
        color: hsl(210 10% 70%);
      }
      .note.error {
        color: hsl(0 80% 72%);
      }
      .hint {
        font-size: 12px;
        line-height: 1.5;
        color: hsl(215 8% 55%);
      }
      .path {
        color: hsl(210 14% 80%);
      }
      input[type="file"] {
        display: none;
      }
      .jobs {
        display: flex;
        flex-direction: column;
      }
      .job {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 6px 12px;
        padding: 12px 0;
        border-top: 1px solid hsl(200 65% 70% / 0.12);
      }
      .job:first-child {
        border-top: 0;
        padding-top: 0;
      }
      .job-name {
        font-size: 13.5px;
        color: hsl(210 14% 86%);
      }
      .job .progress {
        grid-column: 1 / -1;
      }
      .job-detail {
        grid-column: 1 / -1;
        font-size: 12px;
        line-height: 1.5;
        color: hsl(215 8% 58%);
        overflow-wrap: anywhere;
      }
      .job-detail.error {
        color: hsl(0 80% 72%);
      }
      .state {
        justify-self: end;
        align-self: center;
      }
      .state.running {
        color: var(--genome-accent);
        border-color: hsl(190 85% 62% / 0.45);
      }
      .state.ok {
        color: hsl(150 50% 66%);
      }
      .state.error {
        color: hsl(0 80% 72%);
        border-color: hsl(0 80% 72% / 0.45);
      }
      .state.interrupted {
        color: hsl(40 85% 66%);
      }
      .live {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px 14px;
        font-size: 12.5px;
        color: hsl(215 8% 62%);
      }
      .dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        margin-right: 6px;
        border-radius: 50%;
        background: hsl(0 70% 62%);
      }
      .dot.on {
        background: hsl(150 60% 55%);
        box-shadow: 0 0 6px hsl(150 60% 55% / 0.7);
      }
      .live-state {
        display: inline-flex;
        align-items: center;
        color: hsl(210 14% 84%);
      }
      .live .error {
        flex-basis: 100%;
      }
    `,
  ];

  protected updated(changed: Map<string, unknown>): void {
    if (changed.has("narrow")) this.toggleAttribute("narrow", this.narrow);
    if (changed.has("api") && this.api && this._loadedFor !== this.api) {
      this._loadedFor = this.api;
      void this._refreshJobs();
      void this._refreshLive();
      void this._checkLastfm();
    }
  }

  connectedCallback(): void {
    super.connectedCallback();
    this._clock = setInterval(() => (this._now = Math.floor(Date.now() / 1000)), CLOCK_MS);
    if (this._loadedFor && anyRunning(this._jobs)) this._schedulePoll();
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    // a leaked poll would keep firing websocket commands for the life of the session
    clearTimeout(this._poll);
    this._poll = undefined;
    clearInterval(this._clock);
  }

  private _schedulePoll(): void {
    if (this._poll || !this.isConnected) return;
    this._poll = setTimeout(() => {
      this._poll = undefined;
      void this._refreshJobs();
      void this._refreshLive();
    }, POLL_MS);
  }

  private async _refreshJobs(): Promise<void> {
    if (!this.api) return;
    try {
      this._jobs = await this.api.jobs();
      this._jobsError = "";
    } catch (err) {
      this._jobsError = errorMessage(err);
    }
    this._now = Math.floor(Date.now() / 1000);
    // the Apple upload is client-side work the server cannot see yet: keep polling through it
    if (anyRunning(this._jobs) || this._uploading) this._schedulePoll();
  }

  private async _refreshLive(): Promise<void> {
    if (!this.api) return;
    try {
      this._live = await this.api.live();
      this._liveError = "";
    } catch (err) {
      this._liveError = errorMessage(err);
    }
  }

  /** Discovery says "unavailable" exactly when no Last.fm account is set: a free, early hint. */
  private async _checkLastfm(): Promise<void> {
    if (!this.api) return;
    try {
      this._lastfmUnset = (await this.api.discovery()).suggested_state === "unavailable";
    } catch {
      this._lastfmUnset = false;
    }
  }

  private _applyJob(name: keyof GenomeJobs, result: unknown): void {
    const job = result as GenomeJob | null;
    if (this._jobs && job && typeof job === "object" && "state" in job) {
      this._jobs = { ...this._jobs, [name]: { ...job, job: name } };
    }
    this._schedulePoll();
  }

  private async _importLastfm(): Promise<void> {
    if (!this.api || this._lastfmBusy) return;
    this._lastfmBusy = true;
    this._lastfmNote = null;
    try {
      const job = await this.api.importLastfm();
      this._lastfmUnset = false;
      this._lastfmNote = { kind: "info", text: t("panel.import.lastfm_started") };
      this._applyJob("lastfm_import", job);
    } catch (err) {
      const code = (err as { code?: string })?.code;
      if (code === "not_configured") {
        this._lastfmUnset = true;
        this._lastfmNote = {
          kind: "error",
          text: errorMessage(err),
          hint: t("panel.import.lastfm_where"),
        };
      } else {
        this._lastfmNote = { kind: "error", text: errorMessage(err) };
        if (code === "already_running") this._schedulePoll();
      }
    } finally {
      this._lastfmBusy = false;
    }
  }

  private _pickFile(): void {
    this.renderRoot.querySelector<HTMLInputElement>("#apple-file")?.click();
  }

  private async _onFile(e: Event): Promise<void> {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (!file || !this.api) return;
    this._uploading = true;
    this._appleFile = file.name;
    this._appleNote = null;
    try {
      await this.api.importApple(file);
      this._appleNote = { kind: "info", text: t("panel.import.apple_started", { file: file.name }) };
    } catch (err) {
      this._appleNote = { kind: "error", text: errorMessage(err) };
    } finally {
      this._uploading = false;
      void this._refreshJobs();
    }
  }

  private _back(): void {
    this.dispatchEvent(new CustomEvent("navigate", { detail: "" }));
  }

  render() {
    const jobs = this._jobs;
    const lastfmRunning = jobs?.lastfm_import?.state === "running";
    const appleRunning = jobs?.apple_import?.state === "running";
    return html`<div class="page">
      <header>
        <button class="btn back" @click=${this._back}>${iconBack()} ${t("panel.import.back")}</button>
        <h1>${t("panel.import.title")}</h1>
        <p class="subtitle">${t("panel.import.subtitle")}</p>
      </header>
      ${this.isAdmin
        ? nothing
        : html`<p class="hint" role="note">${t("panel.import.admin_only")}</p>`}
      <div class="cards">
        ${this._appleCard(appleRunning)} ${this._lastfmCard(lastfmRunning)}
      </div>
      ${this._statusCard()}
    </div>`;
  }

  private _appleCard(running: boolean) {
    return html`<section class="panel" aria-labelledby="apple-title">
      <div>
        <h2 class="panel-title" id="apple-title">${t("settings.import_apple")}</h2>
        <p class="panel-description">${t("settings.import_apple_hint")}</p>
      </div>
      ${this.isAdmin
        ? html`<input
              id="apple-file"
              type="file"
              accept=".csv,text/csv"
              aria-label=${t("panel.import.apple_choose")}
              @change=${this._onFile}
            />
            <div class="actions">
              <button
                class="btn primary"
                ?disabled=${this._uploading || running}
                @click=${this._pickFile}
              >
                ${this._uploading ? iconLoader() : iconUpload()} ${t("panel.import.apple_choose")}
              </button>
              <span class="file-name">${this._appleFile || t("settings.no_file_chosen")}</span>
            </div>`
        : nothing}
      ${this._uploading
        ? html`<div class="progress indeterminate" role="progressbar"
              aria-label=${t("panel.import.apple_uploading", { file: this._appleFile })}>
              <span></span>
            </div>
            <p class="note" role="status">
              ${t("panel.import.apple_uploading", { file: this._appleFile })}
            </p>`
        : this._note(this._appleNote)}
    </section>`;
  }

  private _lastfmCard(running: boolean) {
    const note = this._lastfmNote;
    return html`<section class="panel" aria-labelledby="lastfm-title">
      <div>
        <h2 class="panel-title" id="lastfm-title">${t("panel.import.lastfm_title")}</h2>
        <p class="panel-description">${t("panel.import.lastfm_hint")}</p>
      </div>
      ${this.isAdmin
        ? html`<div class="actions">
            <button
              class="btn primary"
              ?disabled=${this._lastfmBusy || running}
              @click=${this._importLastfm}
            >
              ${this._lastfmBusy || running ? iconLoader() : nothing}
              ${t("panel.import.lastfm_import_now")}
            </button>
          </div>`
        : nothing}
      ${note
        ? this._note(note)
        : this._lastfmUnset
          ? html`<p class="hint">
              ${t("panel.import.lastfm_unset")}
              <span class="path">${t("panel.import.lastfm_where")}</span>
            </p>`
          : nothing}
    </section>`;
  }

  private _note(note: Note) {
    if (!note) return nothing;
    return html`<p class="note ${note.kind === "error" ? "error" : ""}"
        role=${note.kind === "error" ? "alert" : "status"}>${note.text}</p>
      ${note.hint ? html`<p class="hint path">${note.hint}</p>` : nothing}`;
  }

  private _statusCard() {
    const jobs = this._jobs;
    return html`<section class="panel" aria-labelledby="status-title">
      <div>
        <h2 class="panel-title" id="status-title">${t("panel.import.status_title")}</h2>
        <p class="panel-description">${t("panel.import.status_description")}</p>
      </div>
      ${this._jobsError
        ? html`<p class="note error" role="alert">
            ${t("panel.import.status_error", { error: this._jobsError })}
          </p>`
        : nothing}
      ${jobs
        ? html`<ul class="jobs">
            ${orderedJobs(jobs).map((job) => this._jobRow(job))}
          </ul>`
        : this._jobsError
          ? nothing
          : html`<p class="hint">${t("loading")}</p>`}
      ${this._liveLine()}
    </section>`;
  }

  private _jobRow(job: GenomeJob) {
    const running = job.state === "running";
    const name = jobLabel(job.job);
    const progress = running
      ? job.progress == null
        ? html`<div class="progress indeterminate" role="progressbar"
            aria-label=${t("panel.progress_aria", { job: name })}><span></span></div>`
        : html`<div
            class="progress"
            role="progressbar"
            aria-label=${t("panel.progress_aria", { job: name })}
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow=${Math.round(job.progress)}
          >
            <span style="width:${Math.max(0, Math.min(100, job.progress))}%"></span>
          </div>`
      : nothing;
    return html`<li class="job">
      <span class="job-name">${name}</span>
      <span class="chip state ${job.state}">
        ${running ? iconLoader() : nothing}${stateLabel(job.state)}
        ${running && job.progress != null ? html` · ${Math.round(job.progress)}%` : nothing}
      </span>
      ${progress}
      <p class="job-detail ${job.state === "error" ? "error" : ""}">${jobDetail(job, this._now)}</p>
    </li>`;
  }

  private _liveLine() {
    const live = this._live;
    return html`<div>
      <h3 class="code" style="margin:4px 0 8px">${t("panel.import.live_title")}</h3>
      ${this._liveError
        ? html`<p class="note error">${t("panel.import.live_error", { error: this._liveError })}</p>`
        : !live
          ? html`<p class="hint">${t("loading")}</p>`
          : html`<div class="live" role="status">
              <span class="live-state"
                ><span class="dot ${live.connected ? "on" : ""}" aria-hidden="true"></span
                >${live.connected ? t("panel.import.live_connected") : t("panel.import.live_disconnected")}</span
              >
              ${live.server_version
                ? html`<span>${t("panel.import.live_version", { version: live.server_version })}</span>`
                : nothing}
              <span>${t("panel.import.live_plays", { count: live.plays_captured })}</span>
              <span
                >${live.last_play
                  ? live.last_play_at
                    ? t("panel.import.live_last_play_when", {
                        play: live.last_play,
                        when: relativeTime(live.last_play_at, this._now),
                      })
                    : t("panel.import.live_last_play", { play: live.last_play })
                  : t("panel.import.live_no_play")}</span
              >
              ${live.last_error
                ? html`<span class="error"
                    >${t("panel.import.live_last_error", { error: live.last_error })}</span
                  >`
                : nothing}
            </div>`}
    </div>`;
  }
}

if (!customElements.get("lg-import-view")) customElements.define("lg-import-view", GenomeImportView);
