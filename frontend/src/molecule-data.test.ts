import { describe, expect, it } from "vitest";
import {
  backboneGradientStops,
  baseCode,
  estimatePlays,
  mixGradientStops,
  pairRungsWithGenres,
  secondaryCode,
  secondaryGenres,
  statusForRatio,
  type RungGeometry,
} from "./molecule-data";
import type { GenreShare } from "./types";

function genre(overrides: Partial<GenreShare> = {}): GenreShare {
  return {
    key: "prog_rock",
    label: "Progressive Rock",
    share: 0.2,
    baseline_share: 0.02,
    ratio: 10,
    baseline_known: true,
    contribution: 0.4,
    base_mix: [],
    ...overrides,
  };
}

function rungs(count: number): RungGeometry[] {
  // Descending length so index order already matches rank order, which makes
  // the expected pairing easy to state; other tests exercise a shuffled order.
  return Array.from({ length: count }, (_, i) => ({
    i,
    len: count - i,
  }));
}

describe("secondaryGenres", () => {
  it("excludes base genres and sorts the rest by share desc", () => {
    const bases = [genre({ key: "a", share: 0.5 })];
    const genres = [
      bases[0],
      genre({ key: "b", share: 0.1 }),
      genre({ key: "c", share: 0.3 }),
    ];
    const result = secondaryGenres(genres, bases);
    expect(result.map((g) => g.key)).toEqual(["c", "b"]);
  });

  it("handles zero bases by keeping every genre", () => {
    const genres = [
      genre({ key: "a", share: 0.1 }),
      genre({ key: "b", share: 0.2 }),
    ];
    const result = secondaryGenres(genres, []);
    expect(result.map((g) => g.key)).toEqual(["b", "a"]);
  });
});

describe("pairRungsWithGenres", () => {
  it("pairs the longest rung with the highest-share genre, in rank order", () => {
    const geo = [
      { i: 0, len: 10 },
      { i: 1, len: 50 },
      { i: 2, len: 30 },
    ];
    const genres = [
      genre({ key: "a", share: 0.5 }),
      genre({ key: "b", share: 0.3 }),
    ];
    const pairs = pairRungsWithGenres(geo, genres);
    expect(pairs.get(1)?.key).toBe("a"); // longest rung
    expect(pairs.get(2)?.key).toBe("b"); // second-longest
    expect(pairs.has(0)).toBe(false); // shortest rung: surplus, no genre left
  });

  it("leaves every rung untinted when there are zero genres", () => {
    const pairs = pairRungsWithGenres(rungs(26), []);
    expect(pairs.size).toBe(0);
  });

  it("never repeats a genre across rungs with 1-4 genres", () => {
    for (const n of [1, 2, 3, 4]) {
      const genres = Array.from({ length: n }, (_, i) =>
        genre({ key: `g${i}`, share: 1 - i * 0.1 }),
      );
      const pairs = pairRungsWithGenres(rungs(26), genres);
      expect(pairs.size).toBe(n);
      const keys = [...pairs.values()].map((g) => g.key);
      expect(new Set(keys).size).toBe(n);
    }
  });

  it("pairs all 26 rungs when there are at least 26 genres", () => {
    const genres = Array.from({ length: 30 }, (_, i) =>
      genre({ key: `g${i}`, share: 1 - i * 0.01 }),
    );
    const pairs = pairRungsWithGenres(rungs(26), genres);
    expect(pairs.size).toBe(26);
  });
});

describe("statusForRatio", () => {
  it("classifies overexpressed at >= 2.0", () => {
    expect(statusForRatio(2.0)).toBe("overexpressed");
    expect(statusForRatio(8.5)).toBe("overexpressed");
  });

  it("classifies stable at >= 0.7 and < 2.0", () => {
    expect(statusForRatio(0.7)).toBe("stable");
    expect(statusForRatio(1.9999)).toBe("stable");
  });

  it("classifies underexpressed below 0.7", () => {
    expect(statusForRatio(0.6999)).toBe("underexpressed");
    expect(statusForRatio(0)).toBe("underexpressed");
  });
});

describe("mixGradientStops", () => {
  const colorForIndex = (i: number) => `c${i}`;

  it("returns [] for an empty base_mix rather than fabricating a split", () => {
    expect(mixGradientStops([], colorForIndex)).toEqual([]);
  });

  it("places each stop at the midpoint of its cumulative share", () => {
    const stops = mixGradientStops([0.5, 0.3, 0.2], colorForIndex);
    expect(stops).toEqual([
      { offsetPercent: 25, color: "c0" },
      { offsetPercent: 65, color: "c1" },
      { offsetPercent: 90, color: "c2" },
    ]);
  });
});

describe("backboneGradientStops", () => {
  const colorForIndex = (i: number) => `c${i}`;

  it("returns [] for zero bases", () => {
    expect(backboneGradientStops(0, colorForIndex)).toEqual([]);
  });

  it("returns a single solid stop for one base", () => {
    expect(backboneGradientStops(1, colorForIndex)).toEqual([
      { offsetPercent: 0, color: "c0" },
    ]);
  });

  it("spreads stops evenly across 2-4 bases", () => {
    const stops = backboneGradientStops(4, colorForIndex);
    expect(stops.map((s) => s.color)).toEqual(["c0", "c1", "c2", "c3"]);
    expect(stops[0].offsetPercent).toBeCloseTo(0, 10);
    expect(stops[1].offsetPercent).toBeCloseTo(100 / 3, 10);
    expect(stops[2].offsetPercent).toBeCloseTo(200 / 3, 10);
    expect(stops[3].offsetPercent).toBeCloseTo(100, 10);
  });
});

describe("estimatePlays", () => {
  it("rounds share * total listens", () => {
    expect(estimatePlays(0.17, 4218)).toBe(717);
    expect(estimatePlays(0, 4218)).toBe(0);
  });
});

describe("baseCode", () => {
  it("derives a 3-letter uppercase code from the genre key", () => {
    expect(baseCode("prog_rock")).toBe("PRO");
    expect(baseCode("ambient")).toBe("AMB");
  });

  it("pads short keys", () => {
    expect(baseCode("ok")).toBe("OKX");
  });
});

describe("secondaryCode", () => {
  it("formats a zero-padded rank", () => {
    expect(secondaryCode(0)).toBe("GEN-01");
    expect(secondaryCode(25)).toBe("GEN-26");
  });
});

describe("statusForRatio with no baseline", () => {
  /**
   * The regression this state exists for.
   *
   * Twenty of the fifty-nine genres have no baseline at all, because the reference profile is
   * built from the world's most-played artists and quieter genres never appear in it. Such a
   * genre arrives with ratio 0, which without this case rendered as UNDEREXPRESSED - telling a
   * household that plays a great deal of ambient that they play less of it than average.
   */
  it("reports unmeasured rather than underexpressed", () => {
    expect(statusForRatio(0, false)).toBe("unmeasured");
  });

  it("ignores the ratio entirely when there is no baseline", () => {
    for (const ratio of [0, 0.5, 1, 5, 99]) {
      expect(statusForRatio(ratio, false)).toBe("unmeasured");
    }
  });

  it("still reads a genre the baseline does know", () => {
    expect(statusForRatio(2.5, true)).toBe("overexpressed");
    expect(statusForRatio(1, true)).toBe("stable");
    expect(statusForRatio(0.2, true)).toBe("underexpressed");
  });

  /** Defaulting to "known" keeps every existing caller behaving as it did. */
  it("treats an omitted flag as measured", () => {
    expect(statusForRatio(2.5)).toBe("overexpressed");
  });
});
