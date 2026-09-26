/**
 * A small rotating helix, drawn from the same particles as the molecule.
 *
 * It sits in the dead space of a stat tile and turns at exactly the molecule's rate, so
 * the page reads as one instrument rather than a chart with a decoration stuck on it.
 * It carries no data - a glyph that looked like it encoded something but did not would
 * be worse than an obvious ornament - so it is hidden from assistive technology.
 *
 * It keeps its own clock rather than sharing the molecule's. Same SPEED, independent
 * phase: the molecule stops whenever a callout is open, and a row of tiles freezing
 * because someone hovered a rung two cards away would look like a bug.
 *
 * A port of the fork's GeneGlyph.vue.
 */
import { LitElement, css, html } from "lit";
import { BASE_L, oklch } from "../genome-color";

/**
 * The molecule's rotation rate, from the fork's genome_helix.ts (GENOME_RADIANS_PER_SECOND).
 * Restated here rather than imported so the glyph does not depend on the molecule module.
 */
export const GENOME_RADIANS_PER_SECOND = 0.032;

const W = 64;
const H = 92;
const TURNS = 1.75;
const RADIUS = 17;
const TOP = 10;
const BOTTOM = H - 10;
const STEPS = 46;
const PER_STEP = 2;
/** The same 9-degree lean as the molecule, so the two read as the same object. */
const TILT = (9 * Math.PI) / 180;

interface Speck {
  t: number;
  leg: 0 | 1;
  dR: number;
  dY: number;
  size: number;
  gain: number;
}

/** Deterministic, like the molecule's own field: this glyph must not reshuffle on mount. */
function buildSpecks(): Speck[] {
  let seed = 11;
  const rnd = (): number => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  const out: Speck[] = [];
  for (let i = 0; i < STEPS; i++) {
    for (const leg of [0, 1] as const) {
      for (let k = 0; k < PER_STEP; k++) {
        out.push({
          t: i / STEPS,
          leg,
          dR: (rnd() - 0.5) * 3.2,
          dY: (rnd() - 0.5) * 2.4,
          size: 0.9 + rnd() * 1.5,
          gain: 0.45 + rnd() * 0.75,
        });
      }
    }
  }
  return out;
}
const specks = buildSpecks();

const reduceMotionQuery =
  typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)")
    : null;

export class GeneGlyph extends LitElement {
  static properties = {
    hue: { type: Number },
    intensity: { type: Number },
  };

  /** OKLCH hue in degrees, normally one of the molecule's four base hues. */
  hue = 195;
  /** 0..1 - how far this tile's own figure sits along its range, if it has one. */
  intensity = 0.6;

  private _ctx: CanvasRenderingContext2D | null = null;
  private _raf: number | null = null;
  private _last = 0;
  private _phase = 0;

  static styles = css`
    :host {
      /* 64 x 92 internally, so this keeps the aspect exactly rather than squashing the
         helix a fraction narrower than the one in the plate. */
      display: block;
      width: 44px;
      height: 63px;
      flex: 0 0 auto;
      opacity: 0.9;
      pointer-events: none;
    }
    canvas {
      display: block;
      width: 100%;
      height: 100%;
    }
  `;

  render() {
    return html`<canvas role="presentation" aria-hidden="true"></canvas>`;
  }

  firstUpdated(): void {
    const canvas = this._canvas;
    if (canvas) this._ctx = canvas.getContext("2d");
    this._resize();
    this._start();
  }

  connectedCallback(): void {
    super.connectedCallback();
    // Re-attached after a move: firstUpdated will not run again, so restart the clock here.
    if (this._ctx) this._start();
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    if (this._raf !== null) cancelAnimationFrame(this._raf);
    this._raf = null;
  }

  updated(changed: Map<string, unknown>): void {
    if (changed.has("hue") || changed.has("intensity")) this._draw();
  }

  private get _canvas(): HTMLCanvasElement | null {
    return this.renderRoot.querySelector("canvas");
  }

  private _start(): void {
    if (this._raf !== null || typeof requestAnimationFrame !== "function") return;
    this._last = performance.now();
    this._raf = requestAnimationFrame(this._frame);
  }

  private _frame = (now: number): void => {
    const dt = Math.min(0.05, (now - this._last) / 1000);
    this._last = now;
    if (!document.hidden && !reduceMotionQuery?.matches) {
      this._phase += GENOME_RADIANS_PER_SECOND * dt;
    }
    this._draw();
    this._raf = requestAnimationFrame(this._frame);
  };

  private _resize(): void {
    const canvas = this._canvas;
    if (!canvas) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    this._draw();
  }

  private _draw(): void {
    const canvas = this._canvas;
    const ctx = this._ctx;
    if (!ctx || !canvas) return;
    const scale = canvas.width / W;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    ctx.globalCompositeOperation = "lighter";

    for (const s of specks) {
      const theta = this._phase + 2 * Math.PI * TURNS * s.t + (s.leg ? Math.PI : 0);
      const r = RADIUS + s.dR;
      const rawX = W / 2 + r * Math.cos(theta);
      const rawY = TOP + s.t * (BOTTOM - TOP) + s.dY;
      const midY = (TOP + BOTTOM) / 2;
      const ca = Math.cos(TILT);
      const sa = Math.sin(TILT);
      const dx = rawX - W / 2;
      const dy = rawY - midY;
      const x = W / 2 + dx * ca - dy * sa;
      const y = midY + dx * sa + dy * ca;
      const depth = (Math.sin(theta) + 1) / 2;
      // The intensity floor is high because it has to be: an obscurity index of 0% drove this
      // to near-nothing, and a barely-there glyph reads as a half-drawn graphic rather than as
      // a low reading. The number beside it carries the value; the glyph only has to be there.
      const alpha = s.gain * (0.12 + 0.85 * depth) * (0.62 + 0.38 * this.intensity);
      if (alpha <= 0.01) continue;
      // Lightness barely moves with depth; chroma carries it instead. In OKLCH that keeps
      // the near face reading as "more colour" rather than "brighter", so the glyph does not
      // flash as it turns.
      const l = BASE_L - 0.1 + 0.08 * depth;
      const c = 0.05 + 0.075 * depth;
      ctx.fillStyle = oklch(l, c, this.hue, Math.min(1, alpha));
      ctx.beginPath();
      ctx.arc(x, y, s.size * (0.6 + 0.6 * depth), 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalCompositeOperation = "source-over";
  }
}

if (!customElements.get("lg-gene-glyph")) customElements.define("lg-gene-glyph", GeneGlyph);
