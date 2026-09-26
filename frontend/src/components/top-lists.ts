/**
 * The household's top twenty artists and tracks.
 *
 * Deliberately no share meter. The bar re-encoded what the play count already states, and
 * spent most of each row's width doing it - which left a wide gap between the name and a
 * graphic that added nothing. The rank number carries the ordering instead, and the twenty
 * rows fit a column that scrolls rather than a page that grows.
 *
 * A port of the fork's GenomeTopLists.vue.
 */
import { LitElement, css, html, nothing } from "lit";
import { formatRatio } from "../format";
import { t } from "../i18n";
import { genomeBase, genomeTokens } from "../styles";
import type { ArtistFact, TrackFact } from "../types";

/** Zero-padded so the rank column stays a fixed width and the names line up. */
export function pad(n: number): string {
  return n.toString().padStart(2, "0");
}

type Tab = "artists" | "tracks";
const TABS: Tab[] = ["artists", "tracks"];

export class TopLists extends LitElement {
  static properties = {
    topArtists: { attribute: false },
    topTracks: { attribute: false },
    _tab: { state: true },
  };

  topArtists: ArtistFact[] = [];
  topTracks: TrackFact[] = [];
  private _tab: Tab = "artists";

  static styles = [
    genomeTokens,
    genomeBase,
    css`
      :host {
        display: block;
        min-width: 0;
      }
      .panel {
        height: 100%;
        min-height: 0;
        border-radius: 10px;
      }
      .tabs {
        display: grid;
        grid-template-columns: 1fr 1fr;
        width: 100%;
      }
      .content {
        flex: 1 1 auto;
        min-height: 0;
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      /* The scroller is absolutely positioned, and that is the whole trick.
         Both cards share a grid row, so the row is as tall as its tallest content - which meant
         twenty list rows dictated the height and stretched the three little stat cards to match,
         the exact opposite of what was wanted. Absolutely-positioned content contributes no
         intrinsic height, so the row is sized by the stat column alone and the list scrolls
         inside whatever height that leaves. min-height:0 on each ancestor keeps the flex chain
         from refusing to shrink. */
      .pane {
        position: relative;
        flex: 1 1 auto;
        margin: 0;
        /* A floor, not a height. The three compact tiles alone left room for four rows of a
           list of twenty, which is a scrollbar pretending to be a list. */
        min-height: 290px;
      }
      .pane:focus-visible {
        outline: 1px solid var(--genome-accent);
        outline-offset: 2px;
        border-radius: 6px;
      }
      /* Below the two-column breakpoint the cards stack, so there is no row to match and an
         absolutely-positioned list would collapse to nothing. */
      @media (max-width: 899px) {
        .pane {
          min-height: 340px;
        }
      }
      ol {
        position: absolute;
        inset: 0;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 1px;
        list-style: none;
        margin: 0;
        padding: 0;
        scrollbar-width: thin;
        scrollbar-color: hsl(200 40% 60% / 0.25) transparent;
      }
      li {
        display: flex;
        align-items: baseline;
        gap: 10px;
        padding: 5px 6px;
        border-radius: 6px;
        transition: background-color 120ms ease;
      }
      li:hover {
        background: hsl(205 55% 65% / 0.05);
      }
      .index {
        flex: 0 0 auto;
        font: 600 9.5px/1 var(--genome-mono);
        letter-spacing: 0.12em;
        color: var(--genome-tick);
        width: 2ch;
      }
      .body {
        display: flex;
        flex-direction: column;
        gap: 1px;
        min-width: 0;
      }
      .name {
        font-family: var(--genome-text);
        font-size: 12.5px;
        color: hsl(210 14% 84%);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .meta {
        font: 600 9px/1.3 var(--genome-mono);
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: hsl(215 8% 44%);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    `,
  ];

  render() {
    return html`<section class="panel">
      <h2 class="panel-title">${t("top_lists")}</h2>
      <div class="content">
        <div class="tabs" role="tablist" @keydown=${this._onKey}>
          ${TABS.map(
            (tab) => html`<button
              class="tab"
              role="tab"
              id="tab-${tab}"
              aria-controls="pane-${tab}"
              aria-selected=${this._tab === tab ? "true" : "false"}
              tabindex=${this._tab === tab ? 0 : -1}
              @click=${() => (this._tab = tab)}
            >
              ${t(tab === "artists" ? "top_artists" : "top_tracks")}
            </button>`,
          )}
        </div>
        <div
          class="pane"
          role="tabpanel"
          id="pane-${this._tab}"
          aria-labelledby="tab-${this._tab}"
          tabindex="0"
        >
          ${this._tab === "artists" ? this._artists() : this._tracks()}
        </div>
      </div>
    </section>`;
  }

  private _artists() {
    return html`<ol>
      ${(this.topArtists ?? []).map(
        (artist, i) => html`<li>
          <span class="index">${pad(i + 1)}</span>
          <span class="body">
            <span class="name">${artist.name}</span>
            <span class="meta"
              >${t("plays", { count: artist.plays })}${artist.ratio_vs_average
                ? html` · ${t("vs_average", { ratio: formatRatio(artist.ratio_vs_average) })}`
                : nothing}</span
            >
          </span>
        </li>`,
      )}
    </ol>`;
  }

  private _tracks() {
    return html`<ol>
      ${(this.topTracks ?? []).map(
        (track, i) => html`<li>
          <span class="index">${pad(i + 1)}</span>
          <span class="body">
            <span class="name">${track.name}</span>
            <span class="meta">${track.artist} · ${t("plays", { count: track.plays })}</span>
          </span>
        </li>`,
      )}
    </ol>`;
  }

  /** Arrow keys move between the two tabs, as the Vue (reka-ui) tabs did. */
  private _onKey(e: KeyboardEvent): void {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
    e.preventDefault();
    const i = TABS.indexOf(this._tab);
    const next =
      e.key === "Home"
        ? 0
        : e.key === "End"
          ? TABS.length - 1
          : (i + (e.key === "ArrowRight" ? 1 : -1) + TABS.length) % TABS.length;
    this._tab = TABS[next];
    void this.updateComplete.then(() =>
      (this.renderRoot.querySelector(`#tab-${this._tab}`) as HTMLElement | null)?.focus(),
    );
  }
}

if (!customElements.get("lg-top-lists")) customElements.define("lg-top-lists", TopLists);
