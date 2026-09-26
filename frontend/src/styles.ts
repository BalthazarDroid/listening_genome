/**
 * The page's shared look, ported from the fork's genome.css (kept as src/genome.css.orig).
 *
 * Instrument panel rather than dashboard: hairline borders, corner ticks, uppercase tracked
 * labels, tabular figures, colour only where it carries meaning. Every component adopts
 * `genomeTokens` + `genomeBase`; component-specific rules live beside the component.
 *
 * The page carries its own dark ground whatever Home Assistant's theme is: the molecule is
 * light on darkness and the panels are meant to read as backlit.
 */
import { css } from "lit";

export const genomeTokens = css`
  :host {
    --genome-display: "Syncopate", ui-sans-serif, system-ui, sans-serif;
    --genome-text: "Jura", ui-sans-serif, system-ui, sans-serif;
    --genome-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
    --genome-accent: hsl(190 85% 62%);
    --genome-panel-bg: hsl(215 40% 60% / 0.05);
    --genome-panel-border: hsl(200 65% 70% / 0.3);
    --genome-tick: hsl(190 90% 66% / 0.95);
    --genome-ground: #070a10;
    --genome-fg: #e7e9ee;
    --genome-muted: hsl(215 8% 55%);
    --genome-radius: 14px;
    font-family: var(--genome-text);
    font-feature-settings:
      "tnum" 1,
      "zero" 1;
    color: var(--genome-fg);
  }
`;

export const genomeBase = css`
  * {
    box-sizing: border-box;
  }
  h1,
  h2 {
    font-family: var(--genome-display);
    font-weight: 400;
    letter-spacing: 0.04em;
  }
  h3 {
    font-family: var(--genome-text);
    font-weight: 600;
    letter-spacing: 0.1em;
  }
  p {
    margin: 0;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  /* ---- panels: the corner ticks are the signature ---------------------------------- */
  .panel {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 20px;
    border-radius: var(--genome-radius);
    background: var(--genome-panel-bg);
    border: 1px solid var(--genome-panel-border);
    backdrop-filter: blur(6px);
    box-shadow: inset 0 1px 0 hsl(200 60% 70% / 0.06);
  }
  .panel::before,
  .panel::after {
    content: "";
    position: absolute;
    width: 18px;
    height: 18px;
    pointer-events: none;
    border-color: var(--genome-tick);
    border-style: solid;
    border-radius: inherit;
    filter: drop-shadow(0 0 3px hsl(190 90% 60% / 0.55));
  }
  .panel::before {
    top: 0;
    left: 0;
    border-width: 1px 0 0 1px;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
    border-bottom-left-radius: 0;
  }
  .panel::after {
    bottom: 0;
    right: 0;
    border-width: 0 1px 1px 0;
    border-top-left-radius: 0;
    border-top-right-radius: 0;
    border-bottom-left-radius: 0;
  }
  .panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }
  /* card titles are instrument labels: small, uppercase, tracked, quiet */
  .panel-title {
    margin: 0;
    font-family: var(--genome-display);
    font-weight: 400;
    font-size: 10px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: hsl(215 10% 62%);
  }
  .panel-description {
    margin: 4px 0 0;
    font-family: var(--genome-text);
    font-size: 12px;
    letter-spacing: 0.01em;
    color: hsl(215 8% 48%);
  }

  /* any big figure */
  .figure {
    font-family: var(--genome-display);
    font-weight: 400;
    font-size: 24px;
    line-height: 1.2;
    letter-spacing: 0.005em;
    font-variant-numeric: tabular-nums;
  }
  .code {
    font: 600 9.5px/1 var(--genome-mono);
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: hsl(215 8% 48%);
  }
  .muted {
    color: var(--genome-muted);
  }
  .small {
    font-size: 12px;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: var(--genome-mono);
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    border-radius: 3px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: rgba(255, 255, 255, 0.04);
    color: hsl(215 12% 72%);
    padding: 4px 9px;
  }

  /* ---- buttons ------------------------------------------------------------------ */
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    min-height: 32px;
    padding: 6px 12px;
    font: 600 10.5px/1 var(--genome-mono);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--genome-fg);
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 6px;
    cursor: pointer;
    transition:
      border-color 120ms ease,
      background-color 120ms ease,
      color 120ms ease;
  }
  .btn:hover:not([disabled]) {
    border-color: var(--genome-accent);
    color: var(--genome-accent);
  }
  .btn:focus-visible,
  .icon-btn:focus-visible,
  .tab:focus-visible {
    outline: 1px solid var(--genome-accent);
    outline-offset: 2px;
  }
  .btn[disabled] {
    opacity: 0.45;
    cursor: default;
  }
  .btn.primary {
    background: hsl(190 85% 62% / 0.13);
    border-color: hsl(190 85% 62% / 0.5);
    color: var(--genome-accent);
  }
  .icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    color: hsl(215 12% 72%);
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    cursor: pointer;
  }
  .icon-btn:hover:not([disabled]) {
    color: var(--genome-accent);
    border-color: hsl(190 85% 62% / 0.35);
  }
  .icon-btn[disabled] {
    opacity: 0.45;
    cursor: default;
  }
  .icon {
    width: 16px;
    height: 16px;
    flex: none;
  }
  .spin {
    animation: spin 1s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  /* ---- tabs: the active one is the brighter of the two --------------------------- */
  .tabs {
    display: inline-flex;
    gap: 3px;
    padding: 3px;
    background: hsl(215 40% 60% / 0.06);
    border: 1px solid var(--genome-panel-border);
    border-radius: 7px;
  }
  .tab {
    padding: 6px 10px;
    font: 600 9.5px/1 var(--genome-mono);
    letter-spacing: 0.14em;
    text-transform: uppercase;
    border: 0;
    border-radius: 5px;
    background: transparent;
    color: hsl(215 10% 52%);
    cursor: pointer;
    transition:
      background-color 120ms ease,
      color 120ms ease;
  }
  .tab:hover {
    color: hsl(210 14% 76%);
  }
  .tab[aria-selected="true"] {
    background: hsl(190 85% 62% / 0.13);
    color: var(--genome-accent);
  }

  /* ---- form fields --------------------------------------------------------------- */
  select,
  input[type="text"] {
    min-height: 32px;
    padding: 4px 8px;
    font: 500 13px var(--genome-text);
    color: var(--genome-fg);
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 6px;
  }
  select:focus-visible,
  input:focus-visible {
    outline: 1px solid var(--genome-accent);
  }
  option {
    background: #10141c;
    color: var(--genome-fg);
  }

  /* ---- progress: indeterminate or a value ----------------------------------------- */
  .progress {
    position: relative;
    height: 3px;
    overflow: hidden;
    border-radius: 2px;
    background: rgba(255, 255, 255, 0.08);
  }
  .progress > span {
    position: absolute;
    inset: 0 auto 0 0;
    background: var(--genome-accent);
    box-shadow: 0 0 6px hsl(190 90% 60% / 0.6);
  }
  .progress.indeterminate > span {
    width: 35%;
    animation: slide 1.2s ease-in-out infinite;
  }
  @keyframes slide {
    from {
      left: -35%;
    }
    to {
      left: 100%;
    }
  }

  .error {
    color: hsl(0 80% 72%);
  }
  @media (prefers-reduced-motion: reduce) {
    .spin,
    .progress.indeterminate > span {
      animation-duration: 3s;
    }
  }
`;
