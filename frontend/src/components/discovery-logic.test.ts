import { describe, expect, it } from "vitest";
import { defaultSpeaker, hueFor, markFor, matchPercent, rowKey } from "./discovery-logic";
import { BASE_HUES } from "../genome-color";

const list = {
  players: [
    { entity_id: "media_player.a", name: "A", available: true },
    { entity_id: "media_player.b", name: "B", available: true },
    { entity_id: "media_player.c", name: "C", available: false },
  ],
  last_used: "media_player.b",
};

describe("defaultSpeaker", () => {
  it("prefers the speaker remembered this session", () => {
    expect(defaultSpeaker(list, "media_player.a")).toBe("media_player.a");
  });
  it("falls back to last_used, then the first available", () => {
    expect(defaultSpeaker(list, null)).toBe("media_player.b");
    expect(defaultSpeaker({ ...list, last_used: "media_player.c" }, null)).toBe("media_player.a");
    expect(defaultSpeaker({ ...list, last_used: "gone" }, "media_player.c")).toBe("media_player.a");
  });
  it("returns null when nothing is available", () => {
    expect(defaultSpeaker({ players: [list.players[2]], last_used: null }, null)).toBeNull();
    expect(defaultSpeaker({ players: [], last_used: "x" }, "x")).toBeNull();
  });
});

describe("genre tint", () => {
  it("is stable per key and drawn from the base palette", () => {
    expect(hueFor("ambient")).toBe(hueFor("ambient"));
    expect(BASE_HUES).toContain(hueFor("psychedelic"));
    expect(hueFor(null)).toBe(220);
    expect(markFor("ambient")).toContain("radial-gradient");
  });
});

describe("matchPercent", () => {
  it("clamps to 0..100", () => {
    expect(matchPercent(0.271)).toBe(27);
    expect(matchPercent(1.4)).toBe(100);
    expect(matchPercent(-1)).toBe(0);
    expect(matchPercent(Number.NaN)).toBe(0);
  });
});

describe("rowKey", () => {
  it("distinguishes sections and songs", () => {
    expect(rowKey("cold", "A", "x")).not.toBe(rowKey("suggested", "A", "x"));
    expect(rowKey("cold", "A", "x")).not.toBe(rowKey("cold", "A", "y"));
  });
});
