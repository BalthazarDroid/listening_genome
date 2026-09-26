import { describe, expect, it } from "vitest";
import {
  backboneBands,
  bandAt,
  buildField,
  distanceToSegment,
  HELIX_H,
  HELIX_W,
  mostDivergent,
  project,
  RUNG_COUNT,
  secondaryGenres,
} from "./molecule-helix";
import type { GenreShare } from "./types";

function genre(
  key: string,
  share: number,
  contribution = 0,
  ratio = 1,
): GenreShare {
  return {
    key,
    label: key,
    share,
    baseline_share: 0.01,
    ratio,
    baseline_known: true,
    contribution,
    base_mix: [],
  };
}

describe("buildField", () => {
  it("is identical on every call, because the field is the molecule's identity", () => {
    // A field that reshuffled between mounts would make the page look broken on every
    // reload even though nothing about the data changed.
    const a = buildField();
    const b = buildField();
    expect(a.legs.length).toBe(b.legs.length);
    expect(a.legs[0]).toEqual(b.legs[0]);
    expect(a.legs.at(-1)).toEqual(b.legs.at(-1));
    expect(a.rungs.length).toBe(RUNG_COUNT);
    expect(a.rungs[3].particles[7]).toEqual(b.rungs[3].particles[7]);
  });

  it("differs on a different seed", () => {
    expect(buildField(7).legs[0]).not.toEqual(buildField(8).legs[0]);
  });
});

describe("project", () => {
  it("advancing the phase by a full turn returns to the same point", () => {
    const a = project(0.3, 0, 0);
    const b = project(0.3, 0, Math.PI * 2);
    expect(b.x).toBeCloseTo(a.x, 6);
    expect(b.y).toBeCloseTo(a.y, 6);
    expect(b.depth).toBeCloseTo(a.depth, 6);
  });

  it("puts the two strands half a turn apart", () => {
    const a = project(0.3, 0, 0);
    const b = project(0.3, 1, 0);
    // Opposite sides of the axis: their depths sum to 1 (one near, one far).
    expect(a.depth + b.depth).toBeCloseTo(1, 6);
  });

  it("descends the plate as t grows, and stays inside it", () => {
    const top = project(0, 0, 0.4);
    const bottom = project(1, 0, 0.4);
    expect(bottom.y).toBeGreaterThan(top.y);
    for (const t of [0, 0.25, 0.5, 0.75, 1]) {
      for (const phase of [0, 1, 2, 3]) {
        const p = project(t, 0, phase);
        expect(p.x).toBeGreaterThan(0);
        expect(p.x).toBeLessThan(HELIX_W);
        expect(p.y).toBeGreaterThan(0);
        expect(p.y).toBeLessThan(HELIX_H);
        expect(p.depth).toBeGreaterThanOrEqual(0);
        expect(p.depth).toBeLessThanOrEqual(1);
      }
    }
  });
});

describe("mostDivergent", () => {
  const pool = [
    genre("rock", 0.4, 0.05),
    genre("krautrock", 0.02, 0.4),
    genre("dub", 0.05, 0.2),
    genre("pop", 0.3, 0.01),
  ];

  it("ranks by divergence contribution, not by share", () => {
    // Krautrock is a fortieth of rock's listening but accounts for eight times as much
    // of what makes this household unusual. The bright bands answer "what is unusual".
    expect(mostDivergent(pool, 2).map((g) => g.key)).toEqual([
      "krautrock",
      "dub",
    ]);
  });

  it("drops genres that contribute nothing rather than padding the list", () => {
    const withZero = [...pool, genre("ambient", 0.1, 0)];
    expect(mostDivergent(withZero, 10).map((g) => g.key)).not.toContain(
      "ambient",
    );
  });

  it("returns fewer than asked for when there are fewer to give", () => {
    expect(mostDivergent(pool.slice(0, 2), 6)).toHaveLength(2);
  });

  it("does not mutate its input", () => {
    const order = pool.map((g) => g.key);
    mostDivergent(pool, 2);
    expect(pool.map((g) => g.key)).toEqual(order);
  });
});

describe("secondaryGenres", () => {
  it("excludes the bases", () => {
    const bases = [genre("rock", 0.4)];
    const all = [genre("rock", 0.4), genre("dub", 0.05)];
    expect(secondaryGenres(all, bases).map((g) => g.key)).toEqual(["dub"]);
  });
});

describe("backboneBands", () => {
  it("gives each base a run of the backbone proportional to its share", () => {
    const bands = backboneBands([
      genre("a", 0.3),
      genre("b", 0.1),
      genre("c", 0.1),
    ]);
    expect(bands).toHaveLength(3);
    // Shares are renormalised across the bases, so a's 0.3 of 0.5 is 60% of the strand.
    expect(bands[0].to - bands[0].from).toBeCloseTo(0.6, 6);
    expect(bands[1].to - bands[1].from).toBeCloseTo(0.2, 6);
  });

  it("covers the strand end to end", () => {
    const bands = backboneBands([genre("a", 0.17), genre("b", 0.13)]);
    expect(bands[0].from).toBe(0);
    expect(bands.at(-1)!.to).toBe(1);
  });

  it("returns nothing when there are no bases or no listening", () => {
    expect(backboneBands([])).toEqual([]);
    expect(backboneBands([genre("a", 0)])).toEqual([]);
  });
});

describe("bandAt", () => {
  const bands = backboneBands([genre("a", 0.5), genre("b", 0.5)]);

  it("finds the band a point falls in", () => {
    expect(bandAt(bands, 0.1).index).toBe(0);
    expect(bandAt(bands, 0.9).index).toBe(1);
  });

  it("blends toward the neighbour near a boundary, so there is no visible seam", () => {
    const near = bandAt(bands, 0.48, 0.05);
    expect(near.next).toBe(1);
    expect(near.mix).toBeGreaterThan(0);
    expect(near.mix).toBeLessThanOrEqual(0.5);
  });

  it("does not blend in the middle of a band", () => {
    expect(bandAt(bands, 0.25, 0.05).next).toBe(-1);
  });

  it("reports no band when there are none", () => {
    expect(bandAt([], 0.5).index).toBe(-1);
  });
});

describe("distanceToSegment", () => {
  it("measures perpendicular distance inside the segment", () => {
    expect(distanceToSegment(5, 3, 0, 0, 10, 0)).toBeCloseTo(3, 6);
  });

  it("measures to the nearer end past the segment, not to the infinite line", () => {
    // A pointer well beyond a rung's end must not count as hovering it.
    expect(distanceToSegment(20, 0, 0, 0, 10, 0)).toBeCloseTo(10, 6);
  });

  it("handles a zero-length segment", () => {
    expect(distanceToSegment(4, 5, 1, 1, 1, 1)).toBeCloseTo(5, 6);
  });
});
