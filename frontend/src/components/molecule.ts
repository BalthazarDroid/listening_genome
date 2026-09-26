/**
 * `<lg-molecule>`: the genome's hero visual, a port of the fork's GenomeMolecule.vue.
 *
 * A canvas-rendered, slowly turning double helix of glowing particles. The backbone is
 * banded by the four base genres; every rung carries a secondary genre and takes its colour
 * from that genre's affinity to the bases, mixed in OKLCH. The six most divergent rungs are
 * lit. Hovering, focusing or clicking a rung or strand stops the molecule and shows a
 * callout; beside it sit the base-pair list and two explainers.
 */
import { LitElement, css, html, nothing, svg, unsafeCSS, type PropertyValues } from "lit";
import { t } from "../i18n";
import { genomeBase, genomeTokens } from "../styles";
import type { GenreShare } from "../types";
import {
  backboneBands,
  bandAt,
  buildField,
  distanceToSegment,
  GENOME_RADIANS_PER_SECOND,
  HELIX_H,
  HELIX_W,
  LIT_RUNGS,
  mostDivergent,
  pairRungsWithGenres,
  project,
  secondaryGenres,
  type Band,
  type ParticleField,
} from "../molecule-helix";
import {
  baseCode,
  estimatePlays,
  mixGradientStops,
  secondaryCode,
  statusForRatio,
  type ExpressionStatus,
} from "../molecule-data";
import { formatPercent, formatPlays } from "../format";
import { BASE_HUES, DUST, baseColor, mixColor, mixHue, oklch } from "../genome-color";
import { BAR_MASK_URL } from "../molecule-bar-mask";

// ---- palette ------------------------------------------------------------------

// The palette itself lives in genome-color.ts, computed in OKLCH. The short version of why:
// an HSL palette spaced evenly by hue is not spaced evenly by perceived brightness - green
// outran purple by 3x at the same HSL lightness, and the additive canvas compositing below
// multiplied that head start until every molecule read cyan-to-green regardless of the
// genres behind it.

// The legend markers are the same object as a particle in the molecule: a soft-edged,
// translucent blob, not a flat disc. A radial gradient reproduces the renderer's falloff,
// and a highlight off-centre is what makes it read as a bubble rather than a smudge.
function bubble(index: number): string {
  const core = baseColor(index, 0.8, 0.13);
  const edge = baseColor(index, 0.66, 0.12);
  return (
    `radial-gradient(circle at 38% 34%, rgba(255,255,255,.55) 0%, ` +
    `rgba(255,255,255,0) 34%), ` +
    `radial-gradient(circle at 50% 50%, ${core} 0%, ${core} 38%, ${edge} 62%, ` +
    `transparent 76%)`
  );
}

/** A rung's colour: all four base colours mixed, weighted by the genre's affinity. */
function rungColor(mix: number[], muted = false): string {
  return mixColor(mix, muted);
}

/**
 * A one-line description of what a genre actually is.
 *
 * Returns an empty string for a genre with no entry rather than echoing the key, so a
 * vocabulary that grows ahead of the translations degrades to silence instead of to
 * `genre_desc.some_new_key` printed on the panel.
 */
function genreDesc(key: string): string {
  const path = `molecule.genre_desc.${key}`;
  const text = t(path);
  return text === path ? "" : text;
}

/**
 * Three worked examples for the mixing explainer, built with the real mixing function.
 *
 * Hard-coded swatches would drift the moment the palette moved - which it has, twice. These
 * come out of `rungColor` itself, so the explanation cannot disagree with the molecule.
 */
const MIX_EXAMPLE = {
  pure: rungColor([1, 0, 0, 0]),
  blend: rungColor([0.62, 0.3, 0.05, 0.03]),
  even: rungColor([0.25, 0.25, 0.25, 0.25]),
};

// `base_mix` is [] when cross-genre affinity isn't computable, and absent entirely on a
// payload from an older result schema. Both mean the same thing to the visual.
function baseMix(genre: GenreShare): number[] {
  return genre.base_mix ?? [];
}

const STATUS_COLORS: Record<ExpressionStatus, { c: string; bg: string; bd: string }> = {
  overexpressed: { c: "#e0a23c", bg: "rgba(224,162,60,.10)", bd: "rgba(224,162,60,.42)" },
  stable: { c: "#4ad48a", bg: "rgba(74,212,138,.10)", bd: "rgba(74,212,138,.42)" },
  underexpressed: { c: "#5fa8e8", bg: "rgba(95,168,232,.10)", bd: "rgba(95,168,232,.42)" },
  // Deliberately grey. The other three are readings; this one is the absence of a reading,
  // and giving it a colour of its own would put it on the same footing as them.
  unmeasured: { c: "#8b9099", bg: "rgba(139,144,153,.10)", bd: "rgba(139,144,153,.38)" },
};
/** Status key to the suffix of its translation key. */
const LEGEND_KEY: Record<ExpressionStatus, string> = {
  overexpressed: "over",
  stable: "stable",
  underexpressed: "under",
  unmeasured: "unmeasured",
};
const LEGEND_ORDER: ExpressionStatus[] = ["overexpressed", "stable", "underexpressed", "unmeasured"];

function statusLabel(status: ExpressionStatus): string {
  return t(`molecule.status_${status}`);
}

// ---- canvas sprites ------------------------------------------------------------

const SPRITE = 34;
const spriteCache = new Map<string, HTMLCanvasElement>();
function spriteFor(color: string): HTMLCanvasElement | null {
  const cached = spriteCache.get(color);
  if (cached) return cached;
  if (typeof document === "undefined") return null;
  const c = document.createElement("canvas");
  c.width = c.height = SPRITE;
  const g = c.getContext("2d");
  if (!g) return null;
  const grad = g.createRadialGradient(SPRITE / 2, SPRITE / 2, 0, SPRITE / 2, SPRITE / 2, SPRITE / 2);
  grad.addColorStop(0, color);
  grad.addColorStop(0.45, color);
  grad.addColorStop(1, "transparent");
  g.fillStyle = grad;
  g.beginPath();
  g.arc(SPRITE / 2, SPRITE / 2, SPRITE / 2, 0, Math.PI * 2);
  g.fill();
  spriteCache.set(color, c);
  return c;
}

function blob(
  g: CanvasRenderingContext2D,
  x: number,
  y: number,
  radius: number,
  color: string,
  alpha: number,
): void {
  if (alpha <= 0.004) return;
  const sprite = spriteFor(color);
  if (!sprite) return;
  g.globalAlpha = Math.min(1, alpha);
  const d = radius * 4;
  g.drawImage(sprite, x - d / 2, y - d / 2, d, d);
}

/** The particle field is deterministic, so one copy serves every instance. */
const FIELD: ParticleField = buildField();

const RUNG_HIT_RADIUS = 16;
const LEG_HIT_RADIUS = 13;
const LEG_HIT_SEGMENTS = 60;

interface ActiveTarget {
  rungIndex?: number;
  legKey?: number;
}
function targetsEqual(a: ActiveTarget | null, b: ActiveTarget | null): boolean {
  if (!a || !b) return a === b;
  return a.rungIndex === b.rungIndex && a.legKey === b.legKey;
}

interface HitTarget {
  key: string;
  kind: "leg" | "rung";
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  label: string;
  active: ActiveTarget;
}

interface HudInfo {
  code: string;
  title: string;
  desc: string;
  mix: number[];
  mixLabels: string[];
  mixKnown: boolean;
  status: ExpressionStatus | null;
  anchor: { x: number; y: number };
}

/** A rung's drawing data, derived once per payload rather than once per frame. */
interface RungPaint {
  genre: GenreShare | undefined;
  color: string;
  isLit: boolean;
}

type PopoverName = "legend" | "mix";

export class GenomeMolecule extends LitElement {
  static properties = {
    genres: { attribute: false },
    bases: { attribute: false },
    totalListens: { attribute: false },
    _hovered: { state: true },
    _pinned: { state: true },
    _hitTargets: { state: true },
    _popover: { state: true },
  };

  // Defaulted rather than required: a genome served from a cache written by an older result
  // shape can arrive without `bases`, and a component that throws on a missing field takes
  // its whole card down with it (silently - nothing reaches the server log).
  genres: GenreShare[] = [];
  bases: GenreShare[] = [];
  totalListens = 0;

  private _hovered: ActiveTarget | null = null;
  private _pinned: ActiveTarget | null = null;
  private _hitTargets: HitTarget[] = [];
  private _popover: PopoverName | null = null;

  // ---- derived data (recomputed in willUpdate when the payload changes) ------------
  private _bases: GenreShare[] = [];
  /** Every rung's genre, lit or not. See `_derive`. */
  private _ordered: GenreShare[] = [];
  private _orderedRank = new Map<string, number>();
  private _pairs = new Map<number, GenreShare>();
  private _bands: Band[] = [];
  private _legColors: string[] = [];
  private _rungPaint = new Map<number, RungPaint>();

  // ---- the clock -------------------------------------------------------------------
  private _phase = 0;
  private _raf: number | null = null;
  private _lastFrame = 0;
  private _lastTargetsAt = 0;
  private _reduceMotion = false;
  private _pageHidden = false;
  private _inView = true;
  private _motionQuery: MediaQueryList | null = null;

  private _ctx: CanvasRenderingContext2D | null = null;
  private _resizeObserver: ResizeObserver | null = null;
  private _intersectionObserver: IntersectionObserver | null = null;

  private get _active(): ActiveTarget | null {
    return this._hovered ?? this._pinned;
  }

  // Four reasons to hold still, all of them about not fighting the reader or the battery:
  // the tab is hidden or the card is scrolled away (pure waste), something is hovered or
  // pinned (a callout chasing a moving target is unusable), or the reader has asked the
  // system for less motion.
  private get _spinning(): boolean {
    return !this._pageHidden && this._inView && !this._reduceMotion && this._active === null;
  }

  // ---- lifecycle ---------------------------------------------------------------------

  connectedCallback(): void {
    super.connectedCallback();
    document.addEventListener("visibilitychange", this._onVisibility);
    document.addEventListener("pointerdown", this._onDocumentPointerDown);
    this._onVisibility();
    if (typeof window.matchMedia === "function") {
      this._motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      this._reduceMotion = this._motionQuery.matches;
      this._motionQuery.addEventListener?.("change", this._onMotionPreference);
    }
    // After a re-attach the shadow DOM is already there; firstUpdated will not run again.
    if (this.hasUpdated) this._attachObservers();
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._stopLoop();
    this._resizeObserver?.disconnect();
    this._resizeObserver = null;
    this._intersectionObserver?.disconnect();
    this._intersectionObserver = null;
    document.removeEventListener("visibilitychange", this._onVisibility);
    document.removeEventListener("pointerdown", this._onDocumentPointerDown);
    this._motionQuery?.removeEventListener?.("change", this._onMotionPreference);
  }

  protected willUpdate(changed: PropertyValues): void {
    if (changed.has("genres") || changed.has("bases") || !this.hasUpdated) this._derive();
  }

  protected firstUpdated(): void {
    this._ctx = this._canvas?.getContext("2d") ?? null;
    this._attachObservers();
    this._refreshHitTargets();
  }

  protected updated(changed: PropertyValues): void {
    // Stopping is the moment the hit targets must be exact, because that is when they can be
    // focused and when the callout is anchored.
    if (changed.has("_hovered") || changed.has("_pinned")) this._refreshHitTargets();
    if (changed.has("genres") || changed.has("bases")) this._refreshHitTargets();
    if (
      changed.has("_hovered") ||
      changed.has("_pinned") ||
      changed.has("genres") ||
      changed.has("bases")
    ) {
      this._draw();
      this._syncLoop();
    }
  }

  private _attachObservers(): void {
    const plate = this._plate;
    if (!plate) return;
    if (typeof ResizeObserver !== "undefined" && !this._resizeObserver) {
      this._resizeObserver = new ResizeObserver(() => this._resizeCanvas());
      this._resizeObserver.observe(plate);
    }
    if (typeof IntersectionObserver !== "undefined" && !this._intersectionObserver) {
      this._intersectionObserver = new IntersectionObserver((entries) => {
        this._inView = entries.some((e) => e.isIntersecting);
        this._syncLoop();
      });
      this._intersectionObserver.observe(plate);
    }
    this._resizeCanvas();
    this._syncLoop();
  }

  private get _canvas(): HTMLCanvasElement | null {
    return this.renderRoot.querySelector("canvas");
  }
  private get _plate(): HTMLElement | null {
    return this.renderRoot.querySelector(".genome-plate");
  }

  private _onVisibility = (): void => {
    this._pageHidden = document.visibilityState === "hidden";
    this._syncLoop();
  };
  private _onMotionPreference = (event: MediaQueryListEvent): void => {
    this._reduceMotion = event.matches;
    this._syncLoop();
  };

  // ---- data shaping ------------------------------------------------------------------

  private _derive(): void {
    const genres = Array.isArray(this.genres) ? this.genres : [];
    const bases = Array.isArray(this.bases) ? this.bases : [];
    this._bases = bases;
    const secondary = secondaryGenres(genres, bases);
    /** The lit rungs: the genres that account for most of the household's divergence. */
    const lit = mostDivergent(secondary, LIT_RUNGS);
    const litKeys = new Set(lit.map((g) => g.key));
    // Every rung carries a genre, not just the lit six. The taxonomy has 59 genres, so a real
    // library fills all 26 comfortably - and a rung with nothing behind it is a rung that
    // cannot be hovered, which would leave two thirds of the molecule inert scenery. The
    // divergent six are simply the ones lit; the rest are there to be found.
    const rest = secondary.filter((g) => !litKeys.has(g.key)).sort((a, b) => b.share - a.share);
    this._ordered = [...lit, ...rest];
    // Every secondary genre's position, lit or not. The callout code once used a rank that
    // only knew the six lit genres, so every other rung announced itself as GEN-01.
    this._orderedRank = new Map(this._ordered.map((g, i) => [g.key, i]));
    // Paired once, at phase zero, longest rung first. Pairing by a rung's CURRENT length
    // would reshuffle the genres every frame as the molecule turned, which is nonsense: a
    // genre has a rung.
    this._pairs = pairRungsWithGenres(FIELD.rungs, this._ordered);
    this._bands = backboneBands(bases);

    // Colours are a function of the payload only, so they are worked out here rather than
    // converted from OKLCH for every particle on every frame.
    this._legColors = FIELD.legs.map((p) => this._legColor(p.t));
    this._rungPaint = new Map();
    for (const rung of FIELD.rungs) {
      const genre = this._pairs.get(rung.index);
      const isLit = genre !== undefined && litKeys.has(genre.key);
      // Every paired rung carries its own colour, not just the lit six - a rung you can hover
      // and read should look like something, and the mix is what it IS. The six stay
      // dominant through brightness and their halo, not by being the only coloured thing.
      const color = genre ? rungColor(baseMix(genre), !isLit) : DUST;
      this._rungPaint.set(rung.index, { genre, color, isLit });
    }
  }

  /** The backbone's colour at a point: the band's base, softened toward its neighbour. */
  private _legColor(t: number): string {
    const list = this._bands;
    if (list.length === 0) return DUST;
    const { index, next, mix } = bandAt(list, t);
    const h1 = BASE_HUES[list[index].baseIndex % BASE_HUES.length];
    const hue =
      next === -1 ? h1 : mixHue(h1, BASE_HUES[list[next].baseIndex % BASE_HUES.length], mix);
    // Chromatic enough to read as a band of that base's colour, light enough to stay
    // subordinate to the lit rungs - the backbone is where the listening SITS, the rungs are
    // what makes it unusual.
    return oklch(0.78, 0.075, hue);
  }

  // ---- drawing -------------------------------------------------------------------------

  private _draw(): void {
    const g = this._ctx;
    const canvas = this._canvas;
    if (!g || !canvas) return;

    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, canvas.width, canvas.height);
    const scale = canvas.width / HELIX_W;
    g.setTransform(scale, 0, 0, scale, 0, 0);
    // Additive: overlapping particles accumulate light, which is what gives an open cloud a
    // sense of density without any single particle being opaque.
    g.globalCompositeOperation = "lighter";

    const p = this._phase;
    const activeTarget = this._active;

    FIELD.legs.forEach((particle, i) => {
      const { x, y, depth } = project(
        particle.t,
        particle.leg,
        p,
        particle.dTheta,
        particle.dRadius,
        particle.dY,
      );
      const legActive = activeTarget?.legKey === particle.leg;
      blob(
        g,
        x,
        y,
        particle.size * (0.6 + 0.5 * depth) * (legActive ? 1.2 : 1),
        this._legColors[i] ?? DUST,
        particle.gain * (0.1 + 0.95 * depth) * (legActive ? 0.9 : 0.46),
      );
    });

    for (const rung of FIELD.rungs) {
      const paint = this._rungPaint.get(rung.index);
      const isLit = paint?.isLit ?? false;
      const color = paint?.color ?? DUST;
      const isActive = activeTarget?.rungIndex === rung.index;
      for (const q of rung.particles) {
        const a = project(rung.t, 0, p, 0, q.dRadius, q.dY);
        const b = project(rung.t, 1, p, 0, q.dRadius, q.dY);
        const x = a.x + (b.x - a.x) * q.f;
        const y = a.y + (b.y - a.y) * q.f;
        const depth = a.depth + (b.depth - a.depth) * q.f;
        const dgain = q.gain * (0.1 + 0.95 * depth);
        // A lit rung gets a wide, faint halo under its specks. That halo is most of what
        // makes it read as a band of light rather than a dotted line.
        if (isLit) {
          blob(g, x, y, q.size * 3.4, color, dgain * (isActive ? 0.3 : 0.15));
        }
        blob(
          g,
          x,
          y,
          q.size * (0.55 + 0.5 * depth) * (isActive ? 1.3 : isLit ? 1 : 0.85),
          color,
          dgain * (isLit ? 0.92 : 0.3) * (isActive ? 1.7 : 1),
        );
      }
    }

    g.globalCompositeOperation = "source-over";
    g.globalAlpha = 1;
  }

  private _resizeCanvas(): void {
    const canvas = this._canvas;
    const host = this._plate;
    if (!canvas || !host) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const width = Math.max(1, Math.round(host.clientWidth * dpr));
    const height = Math.round((width * HELIX_H) / HELIX_W);
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    this._draw();
  }

  /**
   * Run the animation loop only while it would change something. The Vue original kept a
   * frame loop going and redrew a still molecule every frame; here a still molecule is drawn
   * once, when whatever stopped it changes, and the loop is not running at all.
   */
  private _syncLoop(): void {
    const run = this.isConnected && this._spinning && typeof requestAnimationFrame === "function";
    if (run && this._raf === null) {
      this._lastFrame = performance.now();
      this._raf = requestAnimationFrame(this._frame);
    } else if (!run) {
      this._stopLoop();
    }
  }

  private _stopLoop(): void {
    if (this._raf !== null) cancelAnimationFrame(this._raf);
    this._raf = null;
  }

  private _frame = (now: number): void => {
    this._raf = null;
    if (!this._spinning) return;
    const dt = Math.min(0.05, Math.max(0, now - this._lastFrame) / 1000);
    this._lastFrame = now;
    this._phase += GENOME_RADIANS_PER_SECOND * dt;
    // Keyboard hit targets follow the molecule, but they only have to be accurate once it has
    // stopped - which is exactly when anything can be focused. Refreshing them every frame
    // would re-render 28 SVG nodes for nobody's benefit.
    if (now - this._lastTargetsAt > 250) {
      this._lastTargetsAt = now;
      this._refreshHitTargets();
    }
    this._draw();
    this._raf = requestAnimationFrame(this._frame);
  };

  // ---- interaction ---------------------------------------------------------------------

  private _setHover(target: ActiveTarget): void {
    if (!targetsEqual(this._hovered, target)) this._hovered = target;
  }
  private _clearHover = (): void => {
    this._hovered = null;
  };
  private _togglePin(target: ActiveTarget): void {
    this._pinned = targetsEqual(this._pinned, target) ? null : target;
  }

  /** Convert a pointer position to plate coordinates. */
  private _toPlate(event: PointerEvent | MouseEvent): { x: number; y: number } | null {
    const host = this._plate;
    if (!host) return null;
    const rect = host.getBoundingClientRect();
    if (rect.width === 0) return null;
    const scale = HELIX_W / rect.width;
    return { x: (event.clientX - rect.left) * scale, y: (event.clientY - rect.top) * scale };
  }

  /** The rung or strand nearest the pointer, or null when it is over empty space. */
  private _pick(x: number, y: number): ActiveTarget | null {
    const p = this._phase;
    let best: ActiveTarget | null = null;
    let bestDistance = Number.POSITIVE_INFINITY;

    for (const rung of FIELD.rungs) {
      if (!this._pairs.has(rung.index)) continue; // unpaired rungs carry nothing to show
      const a = project(rung.t, 0, p);
      const b = project(rung.t, 1, p);
      const d = distanceToSegment(x, y, a.x, a.y, b.x, b.y);
      if (d < bestDistance && d < RUNG_HIT_RADIUS) {
        bestDistance = d;
        best = { rungIndex: rung.index };
      }
    }

    for (const leg of [0, 1] as const) {
      for (let i = 0; i < LEG_HIT_SEGMENTS; i++) {
        const a = project(i / LEG_HIT_SEGMENTS, leg, p);
        const b = project((i + 1) / LEG_HIT_SEGMENTS, leg, p);
        const d = distanceToSegment(x, y, a.x, a.y, b.x, b.y);
        if (d < bestDistance && d < LEG_HIT_RADIUS) {
          bestDistance = d;
          best = { legKey: leg };
        }
      }
    }
    return best;
  }

  private _onPointerMove = (event: PointerEvent): void => {
    const point = this._toPlate(event);
    if (!point) return;
    const hit = this._pick(point.x, point.y);
    if (hit) this._setHover(hit);
    else this._clearHover();
  };

  private _onClick = (event: MouseEvent): void => {
    const point = this._toPlate(event);
    if (!point) return;
    const hit = this._pick(point.x, point.y);
    if (hit) this._togglePin(hit);
  };

  private _onHitKey(event: KeyboardEvent, target: ActiveTarget): void {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      this._togglePin(target);
    }
  }

  private _refreshHitTargets(): void {
    const p = this._phase;
    const out: HitTarget[] = [];
    const legLabel = this._bases.length
      ? t("molecule.leg_aria", { count: this._bases.length })
      : t("molecule.leg_aria_empty");
    for (const leg of [0, 1] as const) {
      const a = project(0, leg, p);
      const b = project(1, leg, p);
      out.push({
        key: `leg-${leg}`,
        kind: "leg",
        x1: a.x,
        y1: a.y,
        x2: b.x,
        y2: b.y,
        label: legLabel,
        active: { legKey: leg },
      });
    }
    for (const rung of FIELD.rungs) {
      const genre = this._pairs.get(rung.index);
      if (!genre) continue;
      const a = project(rung.t, 0, p);
      const b = project(rung.t, 1, p);
      out.push({
        key: `rung-${rung.index}`,
        kind: "rung",
        x1: a.x,
        y1: a.y,
        x2: b.x,
        y2: b.y,
        label: t("molecule.rung_aria", {
          label: genre.label,
          percent: formatPercent(genre.share),
          status: statusLabel(statusForRatio(genre.ratio, genre.baseline_known)),
        }),
        active: { rungIndex: rung.index },
      });
    }
    this._hitTargets = out;
  }

  // ---- popovers (the two explainers) ------------------------------------------------------

  private _togglePopover(name: PopoverName): void {
    this._popover = this._popover === name ? null : name;
  }
  private _onDocumentPointerDown = (event: PointerEvent): void => {
    if (!this._popover) return;
    const path = event.composedPath();
    const inside = path.some(
      (n) => n instanceof HTMLElement && n.dataset && n.dataset.popover === this._popover,
    );
    if (!inside) this._popover = null;
  };
  private _onPopoverKey = (event: KeyboardEvent): void => {
    if (event.key !== "Escape" || !this._popover) return;
    const name = this._popover;
    this._popover = null;
    // Return focus to the trigger, as a dialog-style popover should.
    this.renderRoot.querySelector<HTMLElement>(`[data-popover="${name}"] > button`)?.focus();
  };

  // ---- callout ---------------------------------------------------------------------------

  private _hudInfo(): HudInfo | null {
    const target = this._active;
    if (!target) return null;
    const bases = this._bases;

    if (target.legKey !== undefined) {
      const mid = project(0.5, target.legKey as 0 | 1, this._phase);
      const totalShare = bases.reduce((s, b) => s + b.share, 0);
      const mix = totalShare > 0 ? bases.map((b) => b.share / totalShare) : [];
      return {
        code: "BKB",
        title: t("molecule.backbone_label"),
        desc: bases.length
          ? t("molecule.backbone_desc", { plays: formatPlays(this.totalListens ?? 0) })
          : t("molecule.backbone_desc_empty"),
        mix,
        mixLabels: bases.map((b) => b.label),
        mixKnown: mix.length > 0,
        status: null,
        anchor: { x: mid.x, y: mid.y },
      };
    }

    const rung = FIELD.rungs.find((r) => r.index === target.rungIndex);
    const genre = rung ? this._pairs.get(rung.index) : undefined;
    if (!rung || !genre) return null;
    const a = project(rung.t, 0, this._phase);
    const b = project(rung.t, 1, this._phase);
    const mix = baseMix(genre);
    return {
      code: secondaryCode(this._orderedRank.get(genre.key) ?? 0),
      title: genre.label,
      desc: t("molecule.share_of_listening", {
        percent: formatPercent(genre.share),
        plays: formatPlays(estimatePlays(genre.share, this.totalListens ?? 0)),
      }),
      mix,
      mixLabels: bases.map((b) => b.label),
      mixKnown: mix.length > 0,
      status: statusForRatio(genre.ratio, genre.baseline_known),
      anchor: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 },
    };
  }

  private _hudBarGradient(info: HudInfo): string {
    const stops = mixGradientStops(info.mix, (i) => baseColor(i, 0.7));
    return `linear-gradient(90deg, ${stops
      .map((s) => `${s.color} ${s.offsetPercent.toFixed(1)}%`)
      .join(",")})`;
  }

  // ---- render ----------------------------------------------------------------------------

  private _renderHud(info: HudInfo, hudTopFraction: number) {
    const status = info.status ? STATUS_COLORS[info.status] : null;
    return html`<div
      class="genome-hud on"
      style="--hud-top-fr: ${hudTopFraction}"
      aria-hidden="true"
    >
      <div class="genome-hud__code">${info.code}</div>
      <div class="genome-hud__panel">
        <div class="genome-hud__title">${info.title}</div>
        <div class="genome-hud__desc">${info.desc}</div>
        <div class="genome-hud__bar">
          ${info.mixKnown
            ? html`<div
                class="genome-hud__bar-fill"
                style="background: ${this._hudBarGradient(info)}"
              ></div>`
            : html`<div class="genome-hud__bar-fill genome-hud__bar-fill--neutral"></div>`}
        </div>
        ${info.mixKnown
          ? html`<div class="genome-hud__mix">
              ${info.mix.map(
                (pct, i) => html`<span>
                    <span class="genome-hud__dot" style="background: ${bubble(i)}"></span>
                    ${info.mixLabels[i]}
                  </span>
                  <b>${Math.round(pct * 100)}%</b>`,
              )}
            </div>`
          : html`<div class="genome-hud__mix-unknown">${t("molecule.mix_unknown")}</div>`}
        ${info.status && status
          ? html`<div class="genome-hud__foot">
              <span
                class="genome-hud__status"
                style="color: ${status.c}; background: ${status.bg}; border-color: ${status.bd}"
                >${statusLabel(info.status)}</span
              >
            </div>`
          : nothing}
      </div>
    </div>`;
  }

  private _renderPopover(name: PopoverName, label: string, body: unknown) {
    const open = this._popover === name;
    return html`<div class="popover-anchor" data-popover=${name}>
      <button
        type="button"
        class="genome-legend-trigger"
        aria-haspopup="dialog"
        aria-expanded=${open ? "true" : "false"}
        aria-controls="popover-${name}"
        @click=${() => this._togglePopover(name)}
      >
        ${label}
      </button>
      ${open
        ? html`<div
            id="popover-${name}"
            class="popover popover--${name}"
            role="dialog"
            aria-label=${label}
          >
            ${body}
          </div>`
        : nothing}
    </div>`;
  }

  render() {
    const bases = this._bases;
    const info = this._hudInfo();
    const reticle = info ? info.anchor : null;
    const hudTopFraction = reticle ? Math.max(0.01, reticle.y / HELIX_H - 0.06) : 0;

    return html`<section class="panel">
      <div>
        <h2 class="panel-title">${t("molecule.title")}</h2>
        <p class="panel-description">${t("molecule.subtitle")}</p>
      </div>
      <!-- container-type makes the layout respond to the CARD's width, not the viewport's -
           the page has a sidebar, so those are not the same number. -->
      <div class="genome-shell" @keydown=${this._onPopoverKey}>
        <div class="genome-stage">
          <div
            class="genome-plate"
            @pointermove=${this._onPointerMove}
            @pointerleave=${this._clearHover}
            @click=${this._onClick}
          >
            <canvas class="genome-plate__canvas"></canvas>
            <svg
              class="genome-plate__svg"
              viewBox="0 0 ${HELIX_W} ${HELIX_H}"
              role="group"
              aria-label=${t("molecule.svg_aria")}
            >
              ${reticle
                ? svg`<g class="genome-reticle">
                    <circle cx=${reticle.x} cy=${reticle.y} r="13" fill="none" stroke="#fff"
                      stroke-width="1.1" opacity=".85" />
                    <circle cx=${reticle.x} cy=${reticle.y} r="6" fill="none" stroke="#fff"
                      stroke-width="1.1" opacity=".95" />
                    <circle cx=${reticle.x} cy=${reticle.y} r="1.8" fill="#fff" />
                    <line class="genome-leader" x1=${reticle.x - 13} y1=${reticle.y} x2="-12"
                      y2=${hudTopFraction * HELIX_H + 24} stroke="#fff" stroke-width="1"
                      opacity=".55" />
                  </g>`
                : nothing}
              ${
                /* Keyboard hit targets. The molecule turns, so there is nothing static to
                   attach a hit area to: pointer hover is resolved against the canvas instead
                   (_onPointerMove), and these exist so the same information is reachable by
                   Tab. Their geometry follows the molecule, refreshed at a low rate while it
                   spins and immediately once it stops. */
                this._hitTargets.map(
                  (target) => svg`<line
                    class="genome-hit"
                    x1=${target.x1}
                    y1=${target.y1}
                    x2=${target.x2}
                    y2=${target.y2}
                    stroke="transparent"
                    stroke-width=${target.kind === "leg" ? 26 : 20}
                    stroke-linecap="round"
                    tabindex="0"
                    role="button"
                    aria-label=${target.label}
                    @focus=${() => this._setHover(target.active)}
                    @blur=${this._clearHover}
                    @keydown=${(e: KeyboardEvent) => this._onHitKey(e, target.active)}
                  />`,
                )
              }
            </svg>
          </div>

          <!-- The callout lives in the stage, not the plate: on a wide card it sits in its own
               lane beside the molecule, and only overlays the molecule when the card is too
               narrow to give it a lane of its own. -->
          ${info ? this._renderHud(info, hudTopFraction) : nothing}

          <div class="genome-panel">
            <h3 class="genome-panel__heading">${t("molecule.bases_heading")}</h3>
            <p class="genome-panel__sub">${t("molecule.bases_subtitle")}</p>
            ${bases.length === 0
              ? html`<p class="genome-panel__empty">${t("molecule.no_bases")}</p>`
              : html`<div class="genome-panel__rows">
                  ${bases.map((base, i) => {
                    const desc = genreDesc(base.key);
                    return html`<div class="genome-baserow">
                      <div class="genome-baserow__id">
                        <span class="genome-baserow__dot" style="background: ${bubble(i)}"></span>
                        <div>
                          <div class="genome-baserow__label">${base.label}</div>
                          <div class="genome-baserow__code">${baseCode(base.key)}</div>
                        </div>
                      </div>
                      <div class="genome-baserow__share">${formatPercent(base.share)}</div>
                      ${desc ? html`<div class="genome-baserow__desc">${desc}</div>` : nothing}
                    </div>`;
                  })}
                </div>`}
            <p class="genome-panel__foot">${t("molecule.backbone_explainer")}</p>

            <div class="genome-panel__actions">
              ${this._renderPopover(
                "legend",
                t("molecule.legend_heading"),
                html`<div class="genome-legend">
                  ${LEGEND_ORDER.map(
                    (key) => html`<p class="genome-legend__row">
                      <span
                        class="genome-legend__swatch"
                        style="background: ${STATUS_COLORS[key].c}"
                      ></span>
                      <span>${t(`molecule.legend_${LEGEND_KEY[key]}`)}</span>
                    </p>`,
                  )}
                  <p class="genome-legend__note">${t("molecule.legend_note")}</p>
                </div>`,
              )}
              ${this._renderPopover(
                "mix",
                t("molecule.mix_heading"),
                html`<div class="genome-legend">
                  <p class="genome-legend__lead">${t("molecule.mix_lead")}</p>
                  ${(["pure", "blend", "even"] as const).map(
                    (k) => html`<p class="genome-legend__row">
                      <span
                        class="genome-legend__swatch"
                        style="background: ${MIX_EXAMPLE[k]}"
                      ></span>
                      <span>${t(`molecule.mix_${k}`)}</span>
                    </p>`,
                  )}
                  <p class="genome-legend__note">${t("molecule.mix_note")}</p>
                </div>`,
              )}
            </div>
          </div>
        </div>

        <p class="genome-hint">${t("molecule.hint")}</p>
      </div>
    </section>`;
  }

  static styles = [
    genomeTokens,
    genomeBase,
    css`
      :host {
        display: block;
        --bar-mask: url("${unsafeCSS(BAR_MASK_URL)}");
      }
      .genome-shell {
        container-type: inline-size;
      }
      .genome-hint {
        margin-top: 8px;
        text-align: center;
        font-size: 11px;
        color: var(--genome-muted);
      }

      /* One dark panel spanning the card. The plate, the callout and the base-pair list all
         live inside it, so the space to the right of the molecule is used rather than left as
         an empty margin with content stranded outside the box. */
      .genome-stage {
        /* cqi, not vw: the plate should scale with the CARD, which is what the container
           query below establishes - the page has a sidebar, so vw would undersize it. */
        --stage-h: clamp(380px, 62cqi, 660px);
        /* The plate's aspect ratio is fixed, so its rendered width follows from the stage
           height - which is what lets the callout lanes be plain calc(). */
        --plate-w: calc(var(--stage-h) * 540 / 700);
        --stage-pad: 18px;
        --panel-w: clamp(170px, 20cqi, 230px);
        --lane-gap: 22px;
        position: relative;
        /* Three columns: a callout lane, the molecule, a callout lane. The molecule sits in
           the middle of the card rather than hard left, and the space on both sides is a
           place for information rather than margin. */
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        align-items: stretch;
        height: var(--stage-h);
        padding: var(--stage-pad);
        border-radius: 10px;
        /* The molecule is light on darkness, so the panel carries its own ground rather
           than inheriting the theme's. */
        background: #06070a;
      }
      .genome-plate {
        position: relative;
        grid-column: 2;
        height: 100%;
        aspect-ratio: 540 / 700;
      }
      .genome-plate__canvas,
      .genome-plate__svg {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
      }
      .genome-plate__svg {
        overflow: visible;
      }

      .genome-panel {
        grid-column: 3;
        /* Nearer the molecule than the card's edge: pinned to the far right it read as a
           separate sidebar rather than a legend belonging to the thing beside it. */
        justify-self: start;
        margin-left: var(--lane-gap);
        width: var(--panel-w);
        align-self: start;
        /* Never taller than the plate it floats on: with four base descriptions the panel
           outgrew the plate and its triggers ended up below the artwork. */
        max-height: calc(100% - 24px);
        display: flex;
        flex-direction: column;
        gap: 0;
        padding: 14px 15px 13px;
        background: rgba(255, 255, 255, 0.035);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
      }
      .genome-panel__actions {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      /* Bounding the ROWS rather than the panel keeps the heading, the explainer and both
         triggers visible at all times - the part that scrolls is the part that is a list. It
         takes whatever height the panel has left and scrolls beyond that, bounding itself
         against the plate rather than a guessed max-height. */
      .genome-panel__rows {
        flex: 1 1 auto;
        min-height: 0;
        overflow-y: auto;
        margin-top: 8px;
      }
      .genome-panel__heading {
        margin: 0;
        font-family: var(--genome-text);
        font-weight: 600;
        font-size: 11px;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        color: #8f939d;
      }
      .genome-panel__sub {
        margin-top: 2px;
        font-size: 11px;
        color: #71757e;
      }
      .genome-panel__empty,
      .genome-panel__foot {
        margin-top: 12px;
        font-size: 11px;
        line-height: 1.45;
        color: #71757e;
      }

      .genome-hit {
        cursor: pointer;
      }
      .genome-hit:focus {
        outline: none;
      }
      .genome-hit:focus-visible {
        outline: 2px solid #fff;
        outline-offset: 2px;
      }
      .genome-reticle {
        transition: opacity 0.12s ease;
        pointer-events: none;
      }

      .genome-hud {
        position: absolute;
        pointer-events: none;
        z-index: 8;
        width: clamp(190px, 22cqi, 290px);
        top: min(
          calc(var(--stage-pad) + var(--hud-top-fr) * var(--stage-h)),
          calc(100% - 230px)
        );
        /* The left lane, always. Choosing a side from the reticle looked appealing but is
           degenerate: a rung spans both strands, so its midpoint sits on the axis whichever
           rung it is, and the callout would have flipped on noise. A fixed side also means
           the panel never moves between two rungs, which matters more than symmetry. */
        right: calc(50% + var(--plate-w) / 2 + var(--lane-gap));
      }
      /* The code tab sits at the panel's top-right now that the callout is in the left lane,
         so it points back toward the molecule. */
      .genome-hud__code {
        display: block;
        width: fit-content;
        margin-left: auto;
        margin-bottom: -1px;
        padding: 4px 9px;
        background: rgba(12, 14, 18, 0.94);
        border: 1px solid rgba(255, 255, 255, 0.16);
        border-bottom: 0;
        border-radius: 4px 4px 0 0;
        font:
          600 10px/1 ui-monospace,
          SFMono-Regular,
          Menlo,
          monospace;
        letter-spacing: 0.16em;
        color: #c9cdd6;
      }
      .genome-hud__panel {
        padding: 12px 13px 11px;
        background: rgba(10, 12, 15, 0.94);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.16);
        border-radius: 0 4px 4px 4px;
      }
      .genome-hud__title {
        font: 600 12.5px/1.25 var(--genome-display);
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: #fff;
      }
      .genome-hud__desc {
        font-family: var(--genome-text);
        font-size: 11px;
        color: #8f939d;
        margin-top: 3px;
        line-height: 1.35;
      }
      .genome-hud__bar {
        display: flex;
        /* Taller than a plain progress bar needs to be: it is masked by the speck texture,
           and specks need room to read as specks. */
        height: 15px;
        margin: 9px 0 2px;
      }
      .genome-hud__bar-fill {
        flex: 1;
        mask-image: var(--bar-mask);
        -webkit-mask-image: var(--bar-mask);
        /* auto width, not 100%: stretching the strip to the bar's width squashes every
           bubble into a tall oval. Tiling keeps them round at any bar width. */
        mask-size: auto 100%;
        -webkit-mask-size: auto 100%;
        mask-repeat: repeat-x;
        -webkit-mask-repeat: repeat-x;
      }
      .genome-hud__bar-fill--neutral {
        background: hsl(220 6% 40%);
      }
      .genome-hud__mix {
        margin-top: 10px;
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 3px 10px;
        font-size: 10.5px;
        color: #b9bcc6;
      }
      .genome-hud__mix b {
        color: #fff;
        font-weight: 600;
      }
      .genome-hud__mix-unknown {
        margin-top: 10px;
        font-size: 10.5px;
        color: #b9bcc6;
        font-style: italic;
      }
      .genome-hud__dot {
        display: inline-block;
        width: 11px;
        height: 11px;
        margin-right: 5px;
        vertical-align: -1px;
      }
      .genome-hud__foot {
        display: flex;
        justify-content: flex-end;
        margin-top: 11px;
      }
      .genome-hud__status {
        padding: 5px 11px;
        border-radius: 4px;
        font:
          600 10px/1 ui-monospace,
          Menlo,
          monospace;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        border: 1px solid transparent;
      }

      .genome-baserow {
        /* A grid rather than a flex row, so the description can span the full width
           underneath instead of sharing a line with the share figure. */
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: center;
        gap: 2px 8px;
        padding: 8px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.07);
      }
      .genome-baserow:last-of-type {
        border-bottom: 0;
      }
      .genome-baserow__id {
        display: flex;
        align-items: center;
        gap: 9px;
        min-width: 0;
      }
      .genome-baserow__id > div {
        min-width: 0;
      }
      .genome-baserow__label {
        font-size: 12.5px;
        color: #e7e9ee;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .genome-baserow__share {
        font-size: 12.5px;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        color: #fff;
      }
      .genome-baserow__dot {
        display: inline-block;
        width: 15px;
        height: 15px;
        flex-shrink: 0;
      }
      .genome-baserow__desc {
        grid-column: 1 / -1;
        /* Aligned under the label, not under the dot: the dot belongs to the row, the
           description belongs to the name. */
        padding-left: 24px;
        font-size: 11px;
        line-height: 1.45;
        letter-spacing: 0.01em;
        color: #757982;
      }
      .genome-baserow__code {
        font:
          600 9px/1 ui-monospace,
          Menlo,
          monospace;
        letter-spacing: 0.14em;
        color: #71757e;
        text-transform: uppercase;
        margin-top: 2px;
      }

      /* ---- the two explainers: a trigger and a small popover above it ---------------- */
      /* The popovers hang off the actions row rather than their own trigger, so both open
         to the same edge and stay inside the card whichever trigger opened them. */
      .genome-panel__actions {
        position: relative;
      }
      .genome-legend-trigger {
        margin-top: 10px;
        padding: 0 0 1px;
        font: 600 9.5px/1 var(--genome-mono);
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: #8f939d;
        border: 0;
        border-bottom: 1px dotted rgba(255, 255, 255, 0.3);
        cursor: pointer;
        background: none;
      }
      .genome-legend-trigger:hover,
      .genome-legend-trigger[aria-expanded="true"] {
        color: #c3c7d0;
      }
      .genome-legend-trigger:focus-visible {
        outline: 1px solid var(--genome-accent);
        outline-offset: 3px;
      }
      .popover {
        position: absolute;
        bottom: calc(100% + 8px);
        /* Wide: the panel sits right of the molecule, so open leftward, over the plate. */
        right: 0;
        z-index: 20;
        width: 18rem;
        padding: 16px;
        text-align: left;
        background: #0c0f15;
        border: 1px solid rgba(255, 255, 255, 0.14);
        border-radius: 6px;
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.55);
      }
      .popover--mix {
        width: 20rem;
      }
      .genome-legend {
        display: flex;
        flex-direction: column;
        gap: 9px;
      }
      .genome-legend__row {
        display: grid;
        grid-template-columns: 9px 1fr;
        gap: 9px;
        align-items: start;
        font-family: var(--genome-text);
        font-size: 11.5px;
        line-height: 1.4;
        color: #c3c7d0;
      }
      .genome-legend__swatch {
        width: 9px;
        height: 9px;
        border-radius: 2px;
        margin-top: 3px;
      }
      .genome-legend__note {
        font-family: var(--genome-text);
        font-size: 10.5px;
        line-height: 1.4;
        color: #767b85;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        padding-top: 8px;
      }
      .genome-legend__lead {
        font-family: var(--genome-text);
        font-size: 11.5px;
        line-height: 1.5;
        color: hsl(210 12% 74%);
        margin-bottom: 2px;
      }

      /* Narrow: no room for a lane either side. One column, and the callout stops floating
         entirely - it becomes a block under the molecule. Overlaying it on a small plate hid
         the thing it was describing. The reticle still marks the spot. */
      @container (max-width: 860px) {
        .genome-stage {
          --stage-h: auto;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 18px;
          height: auto;
        }
        .genome-plate {
          order: 1;
          width: 100%;
          max-width: 420px;
          height: auto;
        }
        .genome-hud {
          order: 2;
          position: static;
          width: 100%;
          max-width: 420px;
          left: auto;
          right: auto;
        }
        .genome-hud__code {
          margin-left: 0;
        }
        .genome-panel {
          order: 3;
          width: 100%;
          max-width: 420px;
          max-height: none;
          margin-left: 0;
          justify-self: stretch;
        }
        .genome-leader {
          display: none;
        }
        /* Narrow: the panel is the full width of the stage, so the popover takes that width. */
        .popover,
        .popover--mix {
          left: 0;
          right: 0;
          width: auto;
        }
      }
    `,
  ];
}

if (!customElements.get("lg-molecule")) customElements.define("lg-molecule", GenomeMolecule);

declare global {
  interface HTMLElementTagNameMap {
    "lg-molecule": GenomeMolecule;
  }
}
