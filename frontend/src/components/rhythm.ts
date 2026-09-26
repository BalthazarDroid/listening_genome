/**
 * When the household listens: a 7 x 24 weekday-by-hour grid.
 * A port of the fork's GenomeRhythmHeatmap.vue.
 */
import { LitElement, css, html, svg } from "lit";
import { formatPercent, maxRhythmShare } from "../format";
import { RHYTHM_STEPS, rhythmColor, rhythmStep, rhythmThresholds } from "../genome-color";
import { t } from "../i18n";
import { genomeBase, genomeTokens } from "../styles";
import type { RhythmCell } from "../types";

const cellSize = 16;
const gridX = 22;
const labelOffset = 4;
const hourTicks = [0, 6, 12, 18];
const width = gridX + 24 * cellSize + 4;
const height = labelOffset + 7 * cellSize + 16;
const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

/**
 * Each cell is a solid colour rather than one tint at varying opacity.
 *
 * Opacity let the page background show through, so a quiet hour read as a hole in the card
 * instead of as a low value, and the scale inherited whatever was behind it. A colour taken
 * from the genome ramp keeps the grid reading as one surface and puts the card on the same
 * palette as the molecule above it.
 */
export function rhythmFills(rhythm: RhythmCell[]): (RhythmCell & { fill: string })[] {
  const thresholds = rhythmThresholds(rhythm.map((c) => c.share));
  const max = maxRhythmShare(rhythm);
  return rhythm.map((c) => ({
    ...c,
    fill: rhythmColor(rhythmStep(c.share, thresholds, max) / (RHYTHM_STEPS - 1)),
  }));
}

/** Swatches for the legend, quietest to busiest. */
export function legendSwatches(): string[] {
  return Array.from({ length: RHYTHM_STEPS }, (_, i) => rhythmColor(i / (RHYTHM_STEPS - 1)));
}

export class Rhythm extends LitElement {
  static properties = {
    rhythm: { attribute: false },
  };

  rhythm: RhythmCell[] = [];

  static styles = [
    genomeTokens,
    genomeBase,
    css`
      :host {
        display: block;
        min-width: 0;
      }
      .panel {
        border-radius: 10px;
      }
      /* The grid keeps a legible minimum size and scrolls inside the card on a phone,
         rather than shrinking its cells to specks. */
      .scroll {
        overflow-x: auto;
      }
      svg {
        display: block;
        width: 100%;
        height: auto;
        min-width: 480px;
      }
      text {
        fill: var(--genome-muted);
        font: 9px var(--genome-text);
      }
      .legend {
        display: flex;
        align-items: center;
        gap: 5px;
      }
      .swatch {
        width: 15px;
        height: 9px;
        border-radius: 2px;
      }
    `,
  ];

  render() {
    const labels = WEEKDAYS.map((d) => t(`weekday_${d}`));
    const cells = rhythmFills(this.rhythm ?? []);
    return html`<section class="panel">
      <h2 class="panel-title">${t("rhythm")}</h2>
      <div>
        <div class="scroll">
          <svg viewBox="0 0 ${width} ${height}" role="img" aria-label=${t("rhythm")}>
            ${labels.map(
              (label, i) =>
                svg`<text x="0" y=${labelOffset + i * cellSize + cellSize * 0.7}>${label}</text>`,
            )}
            ${cells.map(
              (c) => svg`<rect
                x=${gridX + c.hour * cellSize}
                y=${labelOffset + c.weekday * cellSize}
                width=${cellSize - 1}
                height=${cellSize - 1}
                rx="1.5"
                fill=${c.fill}
              ><title>${labels[c.weekday]} ${c.hour}:00 · ${formatPercent(c.share)}</title></rect>`,
            )}
            ${hourTicks.map(
              (tick) => svg`<text
                x=${gridX + tick * cellSize + cellSize / 2}
                y=${labelOffset + 7 * cellSize + 10}
                text-anchor="middle"
              >${tick}</text>`,
            )}
          </svg>
        </div>
        <!-- The steps are ranked rather than linear, so a reader has no way to infer the scale
             from the cells alone. The legend is what makes it honest. -->
        <div class="legend" style="margin-top:12px">
          <span class="code">${t("rhythm_quieter")}</span>
          ${legendSwatches().map(
            (swatch) =>
              html`<span class="swatch" style="background:${swatch}" aria-hidden="true"></span>`,
          )}
          <span class="code">${t("rhythm_busier")}</span>
        </div>
      </div>
    </section>`;
  }
}

if (!customElements.get("lg-rhythm")) customElements.define("lg-rhythm", Rhythm);
