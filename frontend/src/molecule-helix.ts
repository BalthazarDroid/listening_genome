/**
 * Pure geometry and selection helpers for the Listening Genome molecule.
 *
 * The molecule is drawn live rather than shipped as an image, because an image cannot
 * rotate about its own axis - spinning a picture turns it like a wheel. Every particle
 * therefore lives in CYLINDRICAL coordinates (a position along the helix, an angular and
 * radial offset), and one `phase` argument turns the whole structure.
 *
 * Everything here is deterministic and free of DOM and canvas, so the maths is testable
 * without a browser; the component owns the drawing and the clock.
 */
import type { GenreShare } from "./types";

export const HELIX_W = 540;
export const HELIX_H = 700;
const TURNS = 3.5;
const RADIUS = 116;
const TOP = 66;
const BOTTOM = HELIX_H - 66;
const CX = HELIX_W / 2;
const TILT = (9 * Math.PI) / 180;

/** Rungs of the ladder. Not every rung carries a genre; the surplus are plain dust. */
export const RUNG_COUNT = 26;
/**
 * How fast the molecule turns. One revolution takes a little over three minutes - drift
 * rather than animation, which is the only speed tolerable on a page left open. Exported
 * because the stat tiles' glyphs turn at the same rate; two rates would read as two
 * unrelated things moving.
 */
export const GENOME_RADIANS_PER_SECOND = 0.032;

/** How many secondary genres are lit at once. See `mostDivergent`. */
export const LIT_RUNGS = 6;

/**
 * Deterministic PRNG.
 *
 * The particle field must be identical on every mount and every machine: it is the
 * molecule's "fingerprint", and a field that reshuffled on reload would make the page feel
 * broken even though nothing changed.
 */
function lcg(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

export interface LegParticle {
  leg: 0 | 1;
  t: number;
  dTheta: number;
  dRadius: number;
  dY: number;
  size: number;
  gain: number;
}
export interface RungParticle {
  f: number;
  dRadius: number;
  dY: number;
  size: number;
  gain: number;
}
export interface RungField {
  index: number;
  t: number;
  particles: RungParticle[];
}
export interface ParticleField {
  legs: LegParticle[];
  rungs: RungField[];
}

const PER_STEP = 3;
const STEPS = 150;
const HAZE_PER_STEP = 2;
const RUNG_PARTICLES = 44;

/**
 * Build the molecule's particle field.
 *
 * :param seed: PRNG seed; the default is the one the design was tuned against.
 */
export function buildField(seed = 7): ParticleField {
  const rnd = lcg(seed);
  // Sum of four uniforms, centred: a cheap bell curve. Uniform jitter makes a tube with
  // hard edges; particles need to thin out at the edge of the cloud, not stop.
  const bell = (): number => (rnd() + rnd() + rnd() + rnd() - 2) * 0.9;

  const legs: LegParticle[] = [];
  for (let i = 0; i < STEPS; i++) {
    const t = i / STEPS;
    for (const leg of [0, 1] as const) {
      for (let k = 0; k < PER_STEP; k++) {
        legs.push({
          leg,
          t,
          dTheta: bell() * 0.028,
          dRadius: bell() * 5.5,
          dY: bell() * 3.4,
          size: 1.4 + rnd() * 2.4,
          gain: 0.5 + rnd(),
        });
      }
      for (let k = 0; k < HAZE_PER_STEP; k++) {
        legs.push({
          leg,
          t,
          dTheta: bell() * 0.085,
          dRadius: bell() * 13,
          dY: bell() * 8,
          size: 1.1 + rnd() * 1.8,
          gain: 0.08 + rnd() * 0.16,
        });
      }
    }
  }

  const rungs: RungField[] = [];
  for (let index = 0; index < RUNG_COUNT; index++) {
    const t = (index + 0.5) / RUNG_COUNT;
    const particles: RungParticle[] = [];
    for (let j = 0; j < RUNG_PARTICLES; j++) {
      particles.push({
        f: (j + 0.5) / RUNG_PARTICLES + bell() * 0.012,
        dRadius: bell() * 3.2,
        dY: bell() * 2.6,
        size: 1.3 + rnd() * 2.2,
        gain: 0.45 + rnd(),
      });
    }
    rungs.push({ index, t, particles });
  }

  return { legs, rungs };
}

export interface Projected {
  x: number;
  y: number;
  /** Depth, 0 at the far face and 1 at the near one. Drives brightness and size. */
  depth: number;
}

function applyTilt(x: number, y: number): [number, number] {
  const dx = x - CX;
  const dy = y - (TOP + BOTTOM) / 2;
  const ca = Math.cos(TILT);
  const sa = Math.sin(TILT);
  return [CX + dx * ca - dy * sa, (TOP + BOTTOM) / 2 + dx * sa + dy * ca];
}

/**
 * Project a point on the helix to plate coordinates.
 *
 * :param t: Position along the molecule, 0 at the top and 1 at the bottom.
 * :param leg: Which strand; the second is half a turn round from the first.
 * :param phase: The molecule's rotation, in radians. This is the only thing that moves.
 */
export function project(
  t: number,
  leg: 0 | 1,
  phase: number,
  dTheta = 0,
  dRadius = 0,
  dY = 0,
): Projected {
  const theta = phase + 2 * Math.PI * TURNS * t + (leg ? Math.PI : 0) + dTheta;
  // Perspective: the ends of the molecule are further away, so they draw in slightly.
  const p = 1 / (1 + 0.18 * Math.abs(t - 0.5) * 2);
  const r = (RADIUS + dRadius) * p;
  const [x, y] = applyTilt(
    CX + r * Math.cos(theta),
    TOP + t * (BOTTOM - TOP) + dY,
  );
  return { x, y, depth: ((r * Math.sin(theta)) / RADIUS + 1) / 2 };
}

/** The genres that are not among the bases, strongest share first. */
export function secondaryGenres(
  genres: GenreShare[],
  bases: GenreShare[],
): GenreShare[] {
  const baseKeys = new Set(bases.map((b) => b.key));
  return genres.filter((g) => !baseKeys.has(g.key));
}

/**
 * The genres that make this household unusual, most first.
 *
 * Ranked by `contribution` - each genre's share of the total Jensen-Shannon divergence -
 * rather than by `ratio`. `ratio` is clamped at 99 and is dominated by genres with a
 * near-zero baseline, so a single play of something obscure would outrank a genuine
 * lifelong preference. `contribution` already weighs how much of the household's
 * distance from the average listener this genre actually accounts for, which is the
 * question the bright bands are answering.
 *
 * :param limit: How many to return.
 */
export function mostDivergent(
  secondary: GenreShare[],
  limit = LIT_RUNGS,
): GenreShare[] {
  return [...secondary]
    .filter((g) => g.contribution > 0)
    .sort((a, b) => b.contribution - a.contribution)
    .slice(0, limit);
}

export interface Band {
  /** Start and end along the molecule, 0..1. */
  from: number;
  to: number;
  /** Index into the bases array, which is also the index into the colour palette. */
  baseIndex: number;
}

/**
 * Divide the backbone into one band per base, each as long as that base's share.
 *
 * The bases' shares are of ALL listening, so they do not sum to 1 - they are renormalised
 * across the four, which is the honest reading: "of your top four, this much is rock".
 * Returns an empty list when there are no bases, in which case the backbone is plain dust.
 */
export function backboneBands(bases: GenreShare[]): Band[] {
  const total = bases.reduce((sum, b) => sum + Math.max(0, b.share), 0);
  if (bases.length === 0 || total <= 0) return [];
  const out: Band[] = [];
  let cursor = 0;
  bases.forEach((b, baseIndex) => {
    const width = Math.max(0, b.share) / total;
    out.push({ from: cursor, to: cursor + width, baseIndex });
    cursor += width;
  });
  // Absorb float drift into the last band so the backbone is covered end to end.
  if (out.length > 0) out[out.length - 1].to = 1;
  return out;
}

/**
 * Which band a point on the backbone falls in, and how far into the crossfade it is.
 *
 * Bands blend into each other over `blend` rather than butting together: a hard colour
 * change across a strand of dust reads as a rendering seam, not as a boundary.
 *
 * :returns: The band index and the neighbour to mix toward (-1 for none), plus the mix
 *   fraction toward that neighbour.
 */
export function bandAt(
  bands: Band[],
  t: number,
  blend = 0.05,
): { index: number; next: number; mix: number } {
  if (bands.length === 0) return { index: -1, next: -1, mix: 0 };
  let index = bands.findIndex((b) => t < b.to);
  if (index === -1) index = bands.length - 1;
  const band = bands[index];
  const distanceToEnd = band.to - t;
  if (index < bands.length - 1 && distanceToEnd < blend) {
    return { index, next: index + 1, mix: 0.5 * (1 - distanceToEnd / blend) };
  }
  const distanceFromStart = t - band.from;
  if (index > 0 && distanceFromStart < blend) {
    return {
      index,
      next: index - 1,
      mix: 0.5 * (1 - distanceFromStart / blend),
    };
  }
  return { index, next: -1, mix: 0 };
}

/**
 * Distance from a point to a line segment, in plate coordinates.
 *
 * Used for hit-testing against a rung, which is a moving target: the rungs are projected
 * afresh every frame, so there is nothing static to attach a DOM hit area to.
 */
export function distanceToSegment(
  px: number,
  py: number,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
): number {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared === 0) return Math.hypot(px - x1, py - y1);
  let u = ((px - x1) * dx + (py - y1) * dy) / lengthSquared;
  u = Math.max(0, Math.min(1, u));
  return Math.hypot(px - (x1 + u * dx), py - (y1 + u * dy));
}

/** Rungs paired to genres by rank: the most divergent genre takes the longest rung. */
export function pairRungsWithGenres(
  rungs: RungField[],
  genres: GenreShare[],
  phase = 0,
): Map<number, GenreShare> {
  const byLength = [...rungs].sort((a, b) => {
    const la = rungLength(a.t, phase);
    const lb = rungLength(b.t, phase);
    return lb - la;
  });
  const out = new Map<number, GenreShare>();
  genres.forEach((genre, i) => {
    const rung = byLength[i];
    if (rung) out.set(rung.index, genre);
  });
  return out;
}

/** A rung's on-screen length at a given phase; longest when the helix faces the viewer. */
export function rungLength(t: number, phase: number): number {
  const a = project(t, 0, phase);
  const b = project(t, 1, phase);
  return Math.hypot(a.x - b.x, a.y - b.y);
}
