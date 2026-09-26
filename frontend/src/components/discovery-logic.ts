/**
 * The pure parts of the discovery card: genre tint, match width, and which speaker the menu
 * starts on. Kept apart from the element so they can be tested without a DOM.
 */
import { BASE_HUES, oklch } from "../genome-color";
import type { Speaker, SpeakerList } from "../types";

/**
 * A stable hue per genre key (ported from GenomeDiscovery.vue).
 *
 * Hashing the key gives every genre a fixed slot in the page's base palette, so two rows that
 * share a genre share a colour. No key -> a neutral blue-grey.
 */
export function hueFor(key: string | null | undefined): number {
  if (!key) return 220;
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (Math.imul(h, 31) + key.charCodeAt(i)) >>> 0;
  return BASE_HUES[h % BASE_HUES.length];
}

/** The strand marker: the same lit bubble as a molecule particle, tinted by genre. */
export function markFor(key: string | null | undefined): string {
  const hue = hueFor(key);
  const core = oklch(0.8, key ? 0.13 : 0.02, hue);
  const edge = oklch(0.64, key ? 0.12 : 0.02, hue);
  return (
    `radial-gradient(circle at 38% 34%, rgba(255,255,255,.5) 0%, rgba(255,255,255,0) 34%), ` +
    `radial-gradient(circle at 50% 50%, ${core} 0%, ${core} 38%, ${edge} 62%, transparent 76%)`
  );
}

/** The match bar's colour. */
export function markLine(key: string | null | undefined): string {
  return oklch(0.72, key ? 0.1 : 0.02, hueFor(key));
}

/** Last.fm's match (0..1, occasionally out of range) as a whole bar-width percentage. */
export function matchPercent(match: number): number {
  if (!Number.isFinite(match)) return 0;
  return Math.round(Math.max(0, Math.min(1, match)) * 100);
}

/**
 * The speaker the menu starts on: the one chosen earlier this session if it is still there and
 * available, else Music Assistant's last-used one, else the first available, else none.
 */
export function defaultSpeaker(list: SpeakerList, remembered: string | null): string | null {
  const usable = (id: string | null): Speaker | undefined =>
    id ? list.players.find((p) => p.entity_id === id && p.available) : undefined;
  return (
    usable(remembered)?.entity_id ??
    usable(list.last_used)?.entity_id ??
    list.players.find((p) => p.available)?.entity_id ??
    null
  );
}

/** A row's identity for per-row play feedback: section + artist + song. */
export function rowKey(section: "suggested" | "cold", artist: string, song: string): string {
  return `${section}\u0000${artist}\u0000${song}`;
}
