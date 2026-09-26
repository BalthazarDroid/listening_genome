/**
 * The page's English strings, carried over from the fork's `listening_genome` translation
 * block (src/strings.json), with the same `{placeholder}` syntax.
 */
import strings from "./strings.json";

type Tree = { [key: string]: string | Tree };

export function t(key: string, values: Record<string, string | number> = {}): string {
  let node: string | Tree | undefined = strings as Tree;
  for (const part of key.split(".")) {
    node = typeof node === "object" ? node[part] : undefined;
  }
  if (typeof node !== "string") return key;
  return node.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in values ? String(values[name]) : match,
  );
}
