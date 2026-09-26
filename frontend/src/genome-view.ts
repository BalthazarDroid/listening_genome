/**
 * The genome page: header, notices, the molecule, the figures, the lists, rhythm, discovery.
 * A port of the fork's ListeningGenomeView.vue; the pieces are the components/ elements.
 */
import { LitElement, css, html, nothing } from "lit";
import { errorMessage, type GenomeApi } from "./api";
import { formatPlays, formatRatio, showResolvingNotice, showUnresolvedNotice } from "./format";
import { t } from "./i18n";
import { iconAlert, iconDna, iconLoader, iconRefresh, iconSettings } from "./icons";
import { genomeBase, genomeTokens } from "./styles";
import type { FailedArtist, GenomeResult } from "./types";
import "./components/molecule";
import "./components/stat-tiles";
import "./components/top-lists";
import "./components/rhythm";
import "./components/discovery";
import "./components/empty-state";

export class GenomeView extends LitElement {
  static properties = {
    api: { attribute: false },
    isAdmin: { type: Boolean },
    narrow: { type: Boolean },
    _genome: { state: true },
    _loading: { state: true },
    _error: { state: true },
    _unresolved: { state: true },
    _dialogOpen: { state: true },
  };

  api!: GenomeApi;
  isAdmin = false;
  narrow = false;
  private _genome: GenomeResult | null = null;
  private _loading = false;
  private _error: string | null = null;
  private _unresolved: FailedArtist[] | null = null;
  private _dialogOpen = false;

  static styles = [
    genomeTokens,
    genomeBase,
    css`
      :host {
        display: block;
      }
      .page {
        display: flex;
        flex-direction: column;
        gap: 24px;
        max-width: 1600px;
        margin: 0 auto;
        padding: 24px;
      }
      :host([narrow]) .page {
        padding: 16px;
        padding-top: 60px;
      }
      header {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }
      h1 {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        margin: 0;
        font-size: 24px;
        text-transform: uppercase;
      }
      h1 .icon {
        width: 20px;
        height: 20px;
        color: var(--genome-accent);
      }
      .subtitle {
        margin-top: 4px;
        font-size: 14px;
        color: var(--genome-muted);
      }
      .actions {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .rule {
        height: 1px;
        margin-top: -12px;
        background: linear-gradient(
          90deg,
          var(--genome-tick),
          rgba(255, 255, 255, 0.05) 42%,
          transparent 78%
        );
      }
      .notice {
        flex-direction: row;
        align-items: flex-start;
        gap: 12px;
        padding: 14px 16px;
      }
      .notice-title {
        margin: 0 0 4px;
        font: 400 13px var(--genome-display);
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }
      .notice-body {
        font-size: 14px;
        color: hsl(215 10% 70%);
      }
      .link {
        padding: 0;
        margin-left: 4px;
        font: inherit;
        font-size: 12px;
        color: var(--genome-accent);
        background: none;
        border: 0;
        cursor: pointer;
        text-decoration: underline;
      }
      .chips {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      /* the three figures stack in one narrow column and the top-twenty list fills a card
         beside them, sized to that column rather than to its own content */
      .columns {
        display: grid;
        grid-template-columns: 1fr;
        align-items: stretch;
        gap: 16px;
      }
      @media (min-width: 900px) {
        .columns {
          grid-template-columns: minmax(230px, 0.85fr) 1.15fr;
        }
      }
      .lower {
        display: grid;
        gap: 24px;
        align-items: start;
      }
      @media (min-width: 1024px) {
        .lower {
          grid-template-columns: 1fr 380px;
        }
      }
      .footer {
        font-size: 12px;
        color: var(--genome-muted);
      }
      .skeleton {
        border-radius: var(--genome-radius);
        background: linear-gradient(
          90deg,
          rgba(255, 255, 255, 0.03),
          rgba(255, 255, 255, 0.07),
          rgba(255, 255, 255, 0.03)
        );
        background-size: 200% 100%;
        animation: shimmer 1.6s linear infinite;
      }
      @keyframes shimmer {
        from {
          background-position: 200% 0;
        }
        to {
          background-position: -200% 0;
        }
      }
      dialog {
        width: min(440px, calc(100vw - 32px));
        max-height: 80vh;
        padding: 20px;
        color: var(--genome-fg);
        background: #0c1119;
        border: 1px solid var(--genome-panel-border);
        border-radius: var(--genome-radius);
      }
      dialog::backdrop {
        background: rgba(0, 0, 0, 0.6);
      }
      .unresolved {
        display: flex;
        flex-direction: column;
        max-height: 46vh;
        overflow-y: auto;
        margin: 8px 0;
      }
      .unresolved li {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 12px;
        padding: 7px 2px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        font-size: 13px;
      }
      .dialog-actions {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        margin-top: 12px;
      }
    `,
  ];

  connectedCallback(): void {
    super.connectedCallback();
    this.toggleAttribute("narrow", this.narrow);
    void this._load();
  }

  updated(changed: Map<string, unknown>): void {
    if (changed.has("narrow")) this.toggleAttribute("narrow", this.narrow);
  }

  private async _load(): Promise<void> {
    this._loading = true;
    this._error = null;
    try {
      this._genome = await this.api.getGenome();
    } catch (err) {
      // "No genome has been computed yet" is the empty state, not an error
      this._genome = null;
      this._error = errorMessage(err);
    } finally {
      this._loading = false;
    }
  }

  private async _rebuild(): Promise<void> {
    this._loading = true;
    this._error = null;
    try {
      this._genome = (await this.api.rebuild()).genome;
    } catch (err) {
      this._error = `${t("rebuild_error")} ${errorMessage(err)}`;
    } finally {
      this._loading = false;
    }
  }

  private async _openUnresolved(): Promise<void> {
    this._dialogOpen = true;
    this._unresolved = null;
    await this.updateComplete;
    this.renderRoot.querySelector("dialog")?.showModal();
    try {
      this._unresolved = await this.api.unresolvedArtists(100);
    } catch {
      this._unresolved = [];
    }
  }

  private _closeDialog(): void {
    this.renderRoot.querySelector("dialog")?.close();
    this._dialogOpen = false;
  }

  private async _retry(): Promise<void> {
    await this.api.retryArtists();
    this._closeDialog();
    await this._load();
  }

  private async _dismiss(): Promise<void> {
    await this.api.dismissUnresolved();
    this._closeDialog();
    await this._load();
  }

  private _navigate(path: string): void {
    this.dispatchEvent(new CustomEvent("navigate", { detail: path }));
  }

  render() {
    return html`<div class="page">
      <header>
        <div>
          <h1>${iconDna()}${t("title")}</h1>
          <p class="subtitle">${t("subtitle")}</p>
        </div>
        <div class="actions">
          <button
            class="icon-btn"
            aria-label=${t("open_settings")}
            title=${t("open_settings")}
            @click=${() => this._navigate("/import")}
          >
            ${iconSettings()}
          </button>
          ${this.isAdmin
            ? html`<button class="btn" ?disabled=${this._loading} @click=${this._rebuild}>
                ${iconRefresh(this._loading ? "icon spin" : "icon")} ${t("rebuild")}
              </button>`
            : nothing}
        </div>
      </header>
      <div class="rule" aria-hidden="true"></div>
      ${this._body()}
    </div>`;
  }

  private _body() {
    const genome = this._genome;
    if (this._loading && !genome) {
      return html`<div class="skeleton" style="height:420px"></div>
        <div class="skeleton" style="height:110px"></div>
        <div class="skeleton" style="height:280px"></div>`;
    }
    if (!genome || genome.stats.total_listens === 0) {
      return html`<lg-empty-state
          .loading=${this._loading}
          .canRebuild=${this.isAdmin}
          @rebuild=${this._rebuild}
          @navigate=${(e: CustomEvent<string>) => this._navigate(e.detail)}
        ></lg-empty-state>
        ${this._error && genome ? html`<p class="error small">${this._error}</p>` : nothing}`;
    }
    return html`
      ${this._error ? html`<p class="error small">${this._error}</p>` : nothing}
      ${this._notices(genome)}
      <lg-molecule
        .genres=${genome.genres}
        .bases=${genome.bases}
        .totalListens=${genome.stats.total_listens}
      ></lg-molecule>
      ${genome.divergence.top_over.length
        ? html`<div class="chips">
            ${genome.divergence.top_over.map(
              (g) =>
                html`<span class="chip"
                  >${g.label} ${t("vs_average", { ratio: formatRatio(g.ratio) })}</span
                >`,
            )}
          </div>`
        : nothing}
      <div class="columns">
        <lg-stat-tiles
          .obscurity=${genome.obscurity}
          .era=${genome.era}
          .loyalty=${genome.loyalty}
        ></lg-stat-tiles>
        <lg-top-lists
          .topArtists=${genome.top_artists}
          .topTracks=${genome.top_tracks}
        ></lg-top-lists>
      </div>
      <div class="lower">
        <lg-rhythm .rhythm=${genome.rhythm}></lg-rhythm>
        <lg-discovery .api=${this.api} .isAdmin=${this.isAdmin}></lg-discovery>
      </div>
      <p class="footer">
        ${t("stats_footer", {
          listens: formatPlays(genome.stats.total_listens),
          artists: formatPlays(genome.stats.distinct_artists),
          tracks: formatPlays(genome.stats.distinct_tracks),
        })}
        ${genome.stale ? html` · ${t("stale_notice")}` : nothing}
      </p>
    `;
  }

  private _notices(genome: GenomeResult) {
    if (showResolvingNotice(genome.stats)) {
      return html`<div class="panel notice" role="status">
        ${iconLoader()}
        <div>
          <p class="notice-title">${t("enriching_title")}</p>
          <p class="notice-body">
            ${t("enriching_body", {
              pending: genome.stats.artists_pending,
              resolved: genome.stats.artists_resolved,
            })}
          </p>
        </div>
      </div>`;
    }
    if (!showUnresolvedNotice(genome.stats)) return nothing;
    return html`<div class="panel notice" role="status">
        ${iconAlert()}
        <div>
          <p class="notice-title">${t("unresolved_title")}</p>
          <p class="notice-body">
            ${t("unresolved_body", { failed: genome.stats.artists_failed })}
            <button class="link" @click=${this._openUnresolved}>${t("unresolved_show")}</button>
          </p>
        </div>
      </div>
      ${this._dialogOpen ? this._dialog() : nothing}`;
  }

  private _dialog() {
    return html`<dialog @close=${() => (this._dialogOpen = false)}>
      <p class="notice-title">${t("unresolved_title")}</p>
      <p class="small muted">${t("unresolved_dialog_hint")}</p>
      <p class="small" style="margin-top:8px">${t("unresolved_what_to_do")}</p>
      ${this._unresolved === null
        ? html`<p class="small muted">${t("loading")}</p>`
        : html`<ul class="unresolved">
            ${this._unresolved.map(
              (a) => html`<li><span>${a.artist_name}</span><span class="code"
                  >${formatAttempt(a.resolved_at)}</span
                ></li>`,
            )}
          </ul>`}
      <div class="dialog-actions">
        <span class="small muted">${t("unresolved_dismiss_hint")}</span>
        <span class="actions">
          ${this.isAdmin
            ? html`<button class="btn" @click=${this._dismiss}>${t("unresolved_dismiss")}</button>
                <button class="btn primary" @click=${this._retry}>${t("unresolved_retry")}</button>`
            : nothing}
          <button class="btn" @click=${this._closeDialog}>Close</button>
        </span>
      </div>
    </dialog>`;
  }
}

/** "last tried 4 hours ago" - the absolute timestamp means nothing to a reader here. */
function formatAttempt(seconds: number): string {
  if (!seconds) return "";
  const hours = Math.max(0, Math.round((Date.now() / 1000 - seconds) / 3600));
  if (hours < 1) return t("attempted_recently");
  if (hours < 48) return t("attempted_hours", { hours });
  return t("attempted_days", { days: Math.round(hours / 24) });
}

if (!customElements.get("lg-genome-view")) customElements.define("lg-genome-view", GenomeView);
