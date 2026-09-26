import type { GenreShare } from "./types";

/**
 * Pure geometry/data helpers for the molecule (components/molecule.ts, ported from GenomeMolecule.vue), split out so the
 * rung<->genre pairing and gradient math can be unit tested without mounting
 * the component. Mirrors the logic in the approved mockup
 * (genome-mock/hud.html) exactly - see that file for the annotated original.
 */

/** The subset of a rung's geometry this module needs. */
export interface RungGeometry {
  i: number;
  len: number;
}

/**
 * The "secondary" genres: everything in `genres` that isn't one of the four
 * (or fewer) `bases`, sorted by share descending - the same order the mockup
 * calls `GEN`.
 */
export function secondaryGenres(
  genres: GenreShare[],
  bases: GenreShare[],
): GenreShare[] {
  const baseKeys = new Set(bases.map((b) => b.key));
  return genres
    .filter((g) => !baseKeys.has(g.key))
    .slice()
    .sort((a, b) => b.share - a.share);
}

/**
 * Pairs rungs with secondary genres by rank: rungs sorted by apparent length
 * descending, genres sorted by share descending, paired in order (exactly as
 * the mockup's `order`/`pair` does it). With fewer genres than rungs, the
 * surplus rungs get no entry in the returned map - the caller must render
 * those untinted and non-interactive rather than repeating a genre.
 */
export function pairRungsWithGenres(
  rungs: RungGeometry[],
  genres: GenreShare[],
): Map<number, GenreShare> {
  const order = [...rungs].sort((a, b) => b.len - a.len);
  const pairs = new Map<number, GenreShare>();
  order.forEach((rung, index) => {
    const genre = genres[index];
    if (genre) pairs.set(rung.i, genre);
  });
  return pairs;
}

/** Overexpressed / Stable / Underexpressed thresholds - a frontend decision
 * per docs/ARCHITECTURE.md §3.4 ("do not invent thresholds in the server"). */
export type ExpressionStatus =
  | "overexpressed"
  | "stable"
  | "underexpressed"
  | "unmeasured";

/**
 * A genre's expression, or "unmeasured" when there is nothing to measure it against.
 *
 * The fourth state is not a nicety. Twenty of the fifty-nine genres have no baseline at all -
 * the reference sample is drawn from the world's most-played artists, so ambient, klezmer and
 * their like are simply absent from it, and no amount of extra sampling changes that. Without
 * this case such a genre took `ratio` 0 and rendered as UNDEREXPRESSED, which states the
 * opposite of the truth about a household that plays a lot of it.
 *
 * :param ratio: The genre's share against the baseline's.
 * :param baselineKnown: Whether the baseline holds enough of this genre to compare against.
 */
export function statusForRatio(
  ratio: number,
  baselineKnown = true,
): ExpressionStatus {
  if (!baselineKnown) return "unmeasured";
  if (ratio >= 2.0) return "overexpressed";
  if (ratio >= 0.7) return "stable";
  return "underexpressed";
}

export interface GradientStop {
  offsetPercent: number;
  color: string;
}

/**
 * Gradient stops for a rung tinted by its `base_mix`: each base gets one stop
 * at the midpoint of its cumulative share, so the gradient reads as a blended
 * bar. Returns `[]` when `baseMix` is empty - the caller renders a neutral
 * colour and an "unknown" callout instead, never a fabricated even split.
 */
export function mixGradientStops(
  baseMix: number[],
  colorForIndex: (index: number) => string,
): GradientStop[] {
  let cumulative = 0;
  return baseMix.map((value, index) => {
    const midpoint = cumulative + value / 2;
    cumulative += value;
    return { offsetPercent: midpoint * 100, color: colorForIndex(index) };
  });
}

/**
 * Gradient stops for the backbone: an even blend of every base (0-4 of them),
 * spread across the strand. With one base the strand is a solid colour; with
 * zero bases (no genome data yet) the caller falls back to a neutral tint.
 */
export function backboneGradientStops(
  baseCount: number,
  colorForIndex: (index: number) => string,
): GradientStop[] {
  if (baseCount <= 0) return [];
  if (baseCount === 1) return [{ offsetPercent: 0, color: colorForIndex(0) }];
  return Array.from({ length: baseCount }, (_, i) => ({
    offsetPercent: (i / (baseCount - 1)) * 100,
    color: colorForIndex(i),
  }));
}

/** Raw play-count estimate for a genre share, given the genome's total listens. */
export function estimatePlays(share: number, totalListens: number): number {
  return Math.round(share * totalListens);
}

/** Short uppercase code chip for a base genre, derived from its key. */
export function baseCode(key: string): string {
  const letters = key.replace(/[^a-z]/gi, "").toUpperCase();
  return (letters.slice(0, 3) || "GEN").padEnd(3, "X");
}

/** Code chip for a secondary (rung) genre: "GEN-01", "GEN-02", ... by rank. */
export function secondaryCode(rank: number): string {
  return `GEN-${String(rank + 1).padStart(2, "0")}`;
}
