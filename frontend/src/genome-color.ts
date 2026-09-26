/**
 * Colour for the Listening Genome, computed in OKLCH.
 *
 * The palette used to be defined in HSL with the four base hues spaced evenly around the
 * wheel. Even spacing in HSL is not even spacing to the eye: at an identical HSL lightness
 * of 62%, green (hue 100) is THREE TIMES the relative luminance of purple (hue 280), and
 * cyan is two and a half times. The molecule then composites its particles additively, so
 * that head start compounds - which is why every render came back reading cyan-to-green
 * whatever the underlying genre mix actually was. Evening the hue spacing did not fix it,
 * because hue spacing was never the problem.
 *
 * OKLCH is perceptually uniform: holding L and C constant and varying only hue gives four
 * colours the eye reads as equally bright. The four hues here measure 1.07x brightest to
 * dimmest, against 3.02x for the HSL palette they replace.
 *
 * Conversion happens here rather than being left to the browser's `oklch()` because the
 * molecule draws to a canvas, and passing sRGB triples to `fillStyle` avoids depending on
 * colour-space support in a 2D context. It is pure and therefore testable without a
 * browser.
 */

/** Linear-light sRGB, before the transfer function. Values outside 0..1 are out of gamut. */
interface LinearRGB {
  r: number;
  g: number;
  b: number;
}

function oklchToLinearSrgb(l: number, c: number, hDeg: number): LinearRGB {
  const h = (hDeg * Math.PI) / 180;
  const a = c * Math.cos(h);
  const b = c * Math.sin(h);

  // OKLab -> LMS', cubed to LMS, then the LMS -> linear sRGB matrix. Constants are from
  // Bjorn Ottosson's definition of the space; they are not tunable parameters.
  const lCube = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const mCube = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const sCube = (l - 0.0894841775 * a - 1.291485548 * b) ** 3;

  return {
    r: 4.0767416621 * lCube - 3.3077115913 * mCube + 0.2309699292 * sCube,
    g: -1.2684380046 * lCube + 2.6097574011 * mCube - 0.3413193965 * sCube,
    b: -0.0041960863 * lCube - 0.7034186147 * mCube + 1.707614701 * sCube,
  };
}

function encodeChannel(value: number): number {
  const clamped = Math.max(0, Math.min(1, value));
  const encoded =
    clamped <= 0.0031308
      ? 12.92 * clamped
      : 1.055 * clamped ** (1 / 2.4) - 0.055;
  return Math.round(encoded * 255);
}

/**
 * An OKLCH colour as an sRGB string.
 *
 * Out-of-gamut components are clipped per channel. That is crude in general, but the
 * palette below is chosen to sit inside sRGB at its working lightness and chroma, so
 * clipping only ever engages for callers pushing chroma deliberately high.
 *
 * :param l: Perceptual lightness, 0..1.
 * :param c: Chroma. Roughly 0 to 0.37 in sRGB, and hue-dependent.
 * :param hDeg: Hue angle in degrees.
 * :param alpha: Optional alpha; omitted produces `rgb(...)` rather than `rgba(...)`.
 */
export function oklch(
  l: number,
  c: number,
  hDeg: number,
  alpha?: number,
): string {
  const lin = oklchToLinearSrgb(l, c, hDeg);
  const r = encodeChannel(lin.r);
  const g = encodeChannel(lin.g);
  const b = encodeChannel(lin.b);
  return alpha === undefined
    ? `rgb(${r} ${g} ${b})`
    : `rgba(${r}, ${g}, ${b}, ${Math.max(0, Math.min(1, alpha))})`;
}

/** True when the colour fits in sRGB without clipping. Used by the palette's own tests. */
export function inSrgbGamut(l: number, c: number, hDeg: number): boolean {
  const { r, g, b } = oklchToLinearSrgb(l, c, hDeg);
  return [r, g, b].every((v) => v >= -0.001 && v <= 1.001);
}

/**
 * The four base hues, in OKLCH degrees: blue, magenta, orange, green.
 *
 * Purely presentational - a slot's colour says nothing about the genre that occupies it, so
 * the palette stays put no matter which genres the household turns out to have.
 *
 * EXACTLY 90 degrees apart, and that is a correctness property rather than a tidiness one.
 * The vector sum in `mixColor` only cancels for an even mix if the four directions cancel,
 * which requires even angular spacing. An earlier set of four hues chosen for gamut and
 * luminance alone sat 95/105/105/55 degrees apart; the narrow 55-degree gap meant those two
 * bases always reinforced, so an even mix - which should come back colourless - resolved
 * into that gap instead. That is the same green-cyan bias the palette was rewritten to cure,
 * reappearing through a different mechanism. There is a test for it.
 *
 * The starting angle is then chosen so that all four sit inside sRGB at the working
 * lightness and chroma, and read as equally bright (1.07x brightest to dimmest).
 */
export const BASE_HUES = [220, 310, 40, 130];

/**
 * Working lightness and chroma for a base colour at full strength.
 *
 * Chroma is bounded by the least forgiving of the four hues: blue at this lightness clips
 * above about 0.135, so the purity curve in `mixColor` is capped below that too.
 */
export const BASE_L = 0.74;
export const BASE_C = 0.115;

/**
 * A base's colour.
 *
 * :param index: Which base, 0..3; wraps.
 * :param l: Lightness override, for dimmer or brighter variants of the same hue.
 * :param c: Chroma override.
 */
export function baseColor(index: number, l = BASE_L, c = BASE_C): string {
  return oklch(l, c, BASE_HUES[index % BASE_HUES.length]);
}

/**
 * Mix the four base colours by weight, as vectors on the OKLCH hue circle.
 *
 * Averaging hue angles numerically would be wrong - the numeric average of cyan and orange
 * is green, which is another base and means something else - and averaging RGB turns any
 * even blend to mud. Each base is instead a vector: its hue for direction, its share of the
 * mix for length. Summing them gives two properties for free.
 *
 *   - The resultant ANGLE is a true blend, so a genre split between cyan and magenta lands
 *     on the violet between them, distinct from either.
 *   - The resultant LENGTH is how lopsided the mix is. A genre belonging equally to all
 *     four cancels to nearly zero and comes back almost colourless, which is the honest
 *     answer: it has no particular allegiance.
 *
 * Chroma carries that length, so purity is visible as saturation while lightness stays put
 * - which is the whole point of doing this in OKLCH. In HSL, dropping saturation also
 * changed apparent brightness, so a muted rung read as a dim rung.
 *
 * :param mix: Weights per base, in base order. Negative weights are treated as zero.
 * :param muted: Drain most of the chroma, for a rung that is not one of the divergent six.
 */
export function mixColor(mix: number[], muted = false): string {
  const total = mix.reduce((sum, w) => sum + Math.max(0, w), 0);
  if (mix.length === 0 || total <= 0) return DUST;

  let vx = 0;
  let vy = 0;
  mix.forEach((weight, i) => {
    const angle = (BASE_HUES[i % BASE_HUES.length] * Math.PI) / 180;
    const w = Math.max(0, weight) / total;
    vx += w * Math.cos(angle);
    vy += w * Math.sin(angle);
  });

  const hue = ((Math.atan2(vy, vx) * 180) / Math.PI + 360) % 360;
  const purity = Math.min(1, Math.hypot(vx, vy));

  // Chroma scales from ZERO, with no floor. A floor looks harmless and is not: an even mix
  // cancels to a purity of zero, at which point the hue angle is undefined (atan2(0, 0) is
  // 0, i.e. red), so any chroma left at that end paints a confident red on a genre that has
  // no allegiance at all. Starting from zero makes the undefined hue invisible, which is the
  // honest rendering of "this genre does not lean anywhere".
  //
  // The exponent lifts the low-purity end back up so that genres with a mild but real lean
  // still show it; without it a linear ramp leaves most real rungs looking washed out.
  //
  // Hue survives muting, so a muted rung is still recognisably itself; only its chroma goes.
  // Lightness is held nearly constant, so the six lit rungs read as "in colour" against
  // "tinted structure" rather than as bright against dark.
  const c = BASE_C * purity ** 0.7 * (muted ? 0.4 : 1);
  // Lightness falls with purity as well as chroma, and it has to. Holding lightness constant
  // meant a rung with no allegiance came back light grey - and on an additively composited
  // canvas, light grey particles stack to pure WHITE, making the least distinctive rungs the
  // brightest objects on the plate. That is the hierarchy exactly backwards. Dropping
  // lightness with purity makes "no particular allegiance" read as faint, which is what it
  // should look like.
  const l = (0.5 + 0.24 * purity) * (muted ? 0.9 : 1);
  return oklch(l, c, hue);
}

/** Uncoloured particles: the structure everything else is suspended in. */
export const DUST = oklch(0.88, 0.006, 240);

/** Shortest-path hue interpolation, so cyan never blends through red to reach orange. */
export function mixHue(a: number, b: number, f: number): number {
  const delta = ((b - a + 540) % 360) - 180;
  return (a + delta * f + 360) % 360;
}

/**
 * How many steps the listening-rhythm scale is quantised into.
 *
 * Discrete rather than continuous, and quantised by RANK rather than by value. A linear
 * ramp against the busiest hour wastes almost its whole range: one or two peak hours sit at
 * the top and every other hour crushes into the bottom fifth, which is why the grid read as
 * two shades of navy with a few bright cells. Ranking spreads the cells across the full ramp,
 * so the shape of a week is actually visible. The exact share stays in each cell's tooltip,
 * which is where a precise figure belongs.
 */
export const RHYTHM_STEPS = 6;

/**
 * Cut points that split the non-empty cells into roughly equal-sized groups.
 *
 * Empty hours are excluded before ranking - in a typical week they are a large share of the
 * grid, and letting them occupy the lower steps would push everything else up and flatten the
 * top end all over again.
 *
 * :param shares: Every cell's share, in any order.
 * :param steps: How many groups to cut into.
 */
export function rhythmThresholds(
  shares: number[],
  steps = RHYTHM_STEPS,
): number[] {
  const active = shares.filter((s) => s > 0).sort((a, b) => a - b);
  if (active.length === 0) return [];
  const cuts: number[] = [];
  for (let i = 1; i < steps; i++) {
    const at = Math.floor((active.length * i) / steps);
    cuts.push(active[Math.min(at, active.length - 1)]);
  }
  return cuts;
}

/**
 * Which step a cell falls in, 0 for empty through `steps - 1` for the busiest group.
 *
 * :param share: This cell's share.
 * :param thresholds: Cut points from `rhythmThresholds`.
 */
export function rhythmStep(
  share: number,
  thresholds: number[],
  max = 0,
): number {
  if (share <= 0) return 0;
  let rank = 1;
  for (const cut of thresholds) {
    if (share > cut) rank++;
  }
  if (max <= 0) return Math.min(rank, RHYTHM_STEPS - 1);
  // Half rank, half raw magnitude. Pure ranking spreads the cells evenly by construction,
  // which puts a full sixth of the grid on the brightest step - a wall of colour that says
  // "these are the peak hours" about twenty-eight different hours. Blending the true value
  // back in pulls the ordinary hours down into the middle of the ramp and leaves the top step
  // to the hours that genuinely earn it, while the rank half still keeps a lopsided week from
  // collapsing into two shades.
  const byRank = rank / (RHYTHM_STEPS - 1);
  const byValue = share / max;
  const blended = 0.5 * byRank + 0.5 * byValue;
  return Math.max(
    1,
    Math.min(RHYTHM_STEPS - 1, Math.round(blended * (RHYTHM_STEPS - 1))),
  );
}

/**
 * The listening-rhythm scale: quiet hours to the household's busiest hour.
 *
 * Travels from the deep blue of the molecule's first base to the green of its fourth, through
 * the cyan between them - two of the four base hues rather than all four. A magnitude scale
 * has to stay legible as an ORDER, and a ramp that visits every hue invents boundaries the
 * data does not have: the eye reads "green" and "orange" as different kinds of thing rather
 * than as more and less. Blue to green climbs without ever reversing direction in hue or
 * lightness, which is what lets it carry more colour than a single-hue ramp while still
 * reading as one continuous scale.
 *
 * :param intensity: 0..1, this cell's position on the scale.
 */
export function rhythmColor(intensity: number): string {
  const t = Math.max(0, Math.min(1, intensity));
  // Lightness and chroma both rise with the value, so the scale survives being printed in
  // grey and stays ordered for a colourblind reader; hue is the decoration, not the encoding.
  const l = 0.26 + 0.48 * t;
  const c = 0.025 + 0.095 * t;
  // Stops at teal rather than running all the way to the base green: at full lightness that
  // green is the loudest colour on the page, and a heatmap is not meant to out-shout the
  // molecule it sits under.
  const h = mixHue(232, 168, t);
  return oklch(l, c, h);
}
