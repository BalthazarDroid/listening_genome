/**
 * The page's two faces (Syncopate for titles and figures, Jura for everything read), served
 * by the integration itself: a local-network panel must not wait on a font CDN.
 *
 * `@font-face` does not work inside a shadow root, so the rules go into the document once.
 */
const FACES: [family: string, weight: number, file: string][] = [
  ["Syncopate", 400, "Syncopate-Regular.woff2"],
  ["Syncopate", 700, "Syncopate-Bold.woff2"],
  ["Jura", 300, "Jura-Light.woff2"],
  ["Jura", 500, "Jura-Medium.woff2"],
  ["Jura", 600, "Jura-SemiBold.woff2"],
];

export function installFonts(base: string): void {
  if (document.getElementById("listening-genome-fonts")) return;
  const style = document.createElement("style");
  style.id = "listening-genome-fonts";
  style.textContent = FACES.map(
    ([family, weight, file]) =>
      `@font-face{font-family:"${family}";font-style:normal;font-weight:${weight};` +
      `font-display:swap;src:url("${base}/fonts/${file}") format("woff2");}`,
  ).join("\n");
  document.head.append(style);
}
