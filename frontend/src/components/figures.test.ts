import { describe, expect, it } from "vitest";
import { RHYTHM_STEPS, rhythmColor } from "../genome-color";
import type { RhythmCell } from "../types";
import { legendSwatches, rhythmFills } from "./rhythm";
import { formatEffective, glyphIntensity } from "./stat-tiles";
import { pad } from "./top-lists";

describe("stat tiles", () => {
  it("keeps one decimal on the effective genre count", () => {
    expect(formatEffective(8)).toBe("8.0");
    expect(formatEffective(8.44)).toBe("8.4");
    expect(formatEffective(undefined)).toBe("—");
  });

  it("clamps glyph intensity to 0..1", () => {
    const [o, e, l] = glyphIntensity(
      { index: 1.4, percentile: 0, threshold_listeners: 0, known_share: 1 },
      { center_of_mass: 1990, spread: 5, buckets: [], known_share: 0.5, artist_year_share: 0 },
      {
        exploration_ratio: 0,
        concentration: 0,
        top_artist_share: 0,
        new_artists_90d: 0,
        repeat_rate: 0,
        effective_genres: 6,
        effective_artists: 0,
        baseline_effective_genres: 0,
      },
    );
    expect([o, e, l]).toEqual([1, 0.5, 0.5]);
  });
});

describe("top lists", () => {
  it("zero-pads ranks to two digits", () => {
    expect(pad(1)).toBe("01");
    expect(pad(20)).toBe("20");
  });
});

describe("rhythm", () => {
  it("paints empty cells the quietest colour and busier hours a different step", () => {
    const cells: RhythmCell[] = [
      { weekday: 0, hour: 0, weight: 0, share: 0 },
      { weekday: 0, hour: 1, weight: 1, share: 0.1 },
      { weekday: 0, hour: 2, weight: 9, share: 0.9 },
    ];
    const fills = rhythmFills(cells);
    expect(fills[0].fill).toBe(rhythmColor(0));
    expect(fills[1].fill).not.toBe(fills[0].fill);
    expect(fills[2].fill).not.toBe(fills[1].fill);
  });

  it("has one legend swatch per step, quietest first", () => {
    const swatches = legendSwatches();
    expect(swatches).toHaveLength(RHYTHM_STEPS);
    expect(swatches[0]).toBe(rhythmColor(0));
  });
});
