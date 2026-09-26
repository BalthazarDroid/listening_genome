// Bundle the panel into ONE module Home Assistant serves from the integration folder.
// HACS installs the repository as-is (it never runs a build), so the built file is committed.
import { build } from "esbuild";

const watch = process.argv.includes("--watch");
const options = {
  entryPoints: ["src/panel.ts"],
  bundle: true,
  format: "esm",
  target: "es2022",
  minify: !watch,
  sourcemap: false,
  legalComments: "eof",
  outfile: "../custom_components/listening_genome/frontend/listening-genome-panel.js",
  logLevel: "info",
};
await build(options);

// the dev harness: the same panel, driven by a fake `hass` answering from fixtures
await build({
  ...options,
  entryPoints: ["dev/harness.ts"],
  minify: false,
  outfile: "dev/dist/harness.js",
});
