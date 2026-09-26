/**
 * The three small readings beside the top lists: obscurity, era centre, eclecticism.
 * A port of the fork's GenomeStatTiles.vue.
 */
import { LitElement, css, html, nothing, svg, type TemplateResult } from "lit";
import { BASE_HUES } from "../genome-color";
import { formatPercent, formatYear } from "../format";
import { t } from "../i18n";
import { genomeBase, genomeTokens } from "../styles";
import type { EraFacts, LoyaltyFacts, ObscurityFacts } from "../types";
import "./gene-glyph";

/**
 * The effective number of genres: "listens across the equivalent of N genres, evenly".
 * One decimal, because the figure is a continuous measure and rounding 8.4 to 8 throws
 * away the only thing that distinguishes two libraries of similar breadth.
 */
export function formatEffective(value: number | undefined): string {
  // A result saved before the entropy figures existed has no value here; a dash is honest
  // where 0.0 would claim a one-genre library.
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "—";
}

/**
 * How brightly each tile's glyph burns, 0..1.
 *
 * Tied loosely to that tile's own figure so the glyphs are not purely decorative, but
 * deliberately not precise: it is a mood, not a reading. The number beside it is the
 * reading.
 */
export function glyphIntensity(
  obscurity: ObscurityFacts,
  era: EraFacts,
  loyalty: LoyaltyFacts,
): [number, number, number] {
  return [
    Math.min(1, obscurity.index),
    Math.min(1, era.known_share),
    Math.min(1, (loyalty.effective_genres ?? 0) / 12),
  ];
}

/** Lucide "info", inlined (icons.ts belongs to the shell). */
const iconInfo = () =>
  svg`<svg class="info-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>`;

type TileKey = "obscurity" | "era" | "eclecticism";

export class StatTiles extends LitElement {
  static properties = {
    obscurity: { attribute: false },
    era: { attribute: false },
    loyalty: { attribute: false },
    _open: { state: true },
  };

  obscurity!: ObscurityFacts;
  era!: EraFacts;
  loyalty!: LoyaltyFacts;
  /** Which tile's explanation is showing - one at a time, like the Vue tooltips. */
  private _open: TileKey | null = null;

  static styles = [
    genomeTokens,
    genomeBase,
    css`
      :host {
        display: grid;
        grid-template-columns: 1fr;
        grid-auto-rows: max-content;
        align-content: start;
        gap: 12px;
      }
      /* Compact: these are three small readings, not three panels. */
      .panel {
        gap: 0;
        padding: 13px 15px;
        /* rounded-lg on the Vue Card */
        border-radius: 10px;
      }
      /* The open tile has to sit above its later siblings: each panel's backdrop-filter is its
         own stacking context, so a popover would otherwise slide under the next tile. */
      .panel.open {
        z-index: 2;
      }
      .panel.low .tile {
        opacity: 0.6;
      }
      .tile {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      /* Text left, glyph after. The figure is what the tile is for, so it starts at the
         same edge as every other tile's; the glyph fills the space that was empty. */
      .body {
        display: flex;
        flex-direction: column;
        gap: 2px;
        /* Only as wide as its text, so the leftover width is a real gap the glyph can sit in
           the middle of. */
        flex: 0 1 auto;
        min-width: 0;
        text-align: left;
        order: 0;
      }
      /* The glyph is first in the DOM (it is decoration, and screen readers skip it), so
         the visual order has to be stated. Auto margins on BOTH sides: it centres itself in
         whatever space the text has not taken, rather than hugging either edge. */
      lg-gene-glyph {
        order: 1;
        margin-inline: auto;
        width: 34px;
        height: 49px;
      }
      .label {
        display: flex;
        align-items: center;
        gap: 6px;
      }
      /* The eclecticism tile's caption is the longest on the row; let it wrap rather than
         squeeze the glyph's lane down to nothing. */
      .body .code {
        white-space: normal;
        line-height: 1.45;
        max-width: 22ch;
      }
      .figure {
        font-size: 1.35rem;
        line-height: 1.15;
      }
      .info {
        display: inline-flex;
        padding: 0;
        margin: 0;
        color: var(--genome-muted);
        background: none;
        border: 0;
        border-radius: 50%;
        cursor: help;
      }
      .info:focus-visible {
        outline: 1px solid var(--genome-accent);
        outline-offset: 2px;
      }
      .info-icon {
        width: 14px;
        height: 14px;
      }
      /* Anchored to the tile rather than the icon so it can never run off a phone screen. */
      .tip {
        position: absolute;
        top: calc(100% + 6px);
        left: 12px;
        right: 12px;
        max-width: 320px;
        padding: 8px 11px;
        font: 400 12px/1.45 var(--genome-text);
        letter-spacing: 0.01em;
        color: hsl(210 14% 84%);
        background: #0c1119;
        border: 1px solid var(--genome-panel-border);
        border-radius: 6px;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.5);
      }
    `,
  ];

  render() {
    if (!this.obscurity || !this.era || !this.loyalty) return nothing;
    const intensity = glyphIntensity(this.obscurity, this.era, this.loyalty);
    const lowConfidence = this.obscurity.known_share < 0.5;
    const baseline = this.loyalty.baseline_effective_genres ?? 0;
    return html`
      ${this._tile(
        "obscurity",
        BASE_HUES[0],
        intensity[0],
        t("obscurity"),
        t("obscurity_tooltip"),
        formatPercent(this.obscurity.index),
        lowConfidence ? t("low_confidence") : null,
        lowConfidence,
      )}
      ${this._tile(
        "era",
        BASE_HUES[3],
        intensity[1],
        t("era_center"),
        t("era_center_tooltip"),
        formatYear(this.era.center_of_mass),
        `± ${Math.round(this.era.spread)} ${t("years")}`,
      )}
      ${this._tile(
        "eclecticism",
        BASE_HUES[1],
        intensity[2],
        t("eclecticism"),
        t("eclecticism_tooltip"),
        formatEffective(this.loyalty.effective_genres),
        baseline > 0
          ? t("eclecticism_vs_average", { baseline: formatEffective(baseline) })
          : t("eclecticism_no_baseline"),
      )}
    `;
  }

  private _tile(
    key: TileKey,
    hue: number,
    intensity: number,
    label: string,
    tooltip: string,
    figure: string,
    caption: string | null,
    low = false,
  ): TemplateResult {
    const open = this._open === key;
    const tipId = `tip-${key}`;
    const show = () => (this._open = key);
    const hide = () => {
      if (this._open === key) this._open = null;
    };
    return html`<div
      class="panel ${open ? "open" : ""} ${low ? "low" : ""}"
      @mouseleave=${hide}
    >
      <div class="tile">
        <lg-gene-glyph .hue=${hue} .intensity=${intensity}></lg-gene-glyph>
        <div class="body">
          <div class="label">
            <span class="code">${label}</span>
            <button
              class="info"
              aria-label=${tooltip}
              aria-describedby=${open ? tipId : nothing}
              @mouseenter=${show}
              @focus=${show}
              @blur=${hide}
              @click=${() => (this._open = open ? null : key)}
              @keydown=${(e: KeyboardEvent) => e.key === "Escape" && hide()}
            >
              ${iconInfo()}
            </button>
          </div>
          <div class="figure">${figure}</div>
          ${caption ? html`<div class="code">${caption}</div>` : nothing}
        </div>
      </div>
      ${open ? html`<div class="tip" id=${tipId} role="tooltip">${tooltip}</div>` : nothing}
    </div>`;
  }
}

if (!customElements.get("lg-stat-tiles")) customElements.define("lg-stat-tiles", StatTiles);
