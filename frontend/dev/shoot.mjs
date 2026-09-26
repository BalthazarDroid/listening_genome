// Screenshot the dev harness: node dev/shoot.mjs <out.png> [query] [width] [height] [fullPage]
import { chromium } from "playwright-core";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";

const [out, query = "", width = "1400", height = "1000", full = "1"] = process.argv.slice(2);
const root = path.resolve(new URL("..", import.meta.url).pathname, "..");
const types = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".woff2": "font/woff2", ".png": "image/png" };
const server = http.createServer((req, res) => {
  const file = path.join(root, decodeURIComponent(new URL(req.url, "http://x").pathname));
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { "content-type": types[path.extname(file)] ?? "application/octet-stream" });
    res.end(data);
  });
}).listen(0);
const port = server.address().port;
const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const page = await browser.newPage({ viewport: { width: +width, height: +height } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
await page.goto(`http://localhost:${port}/frontend/dev/index.html?${query}`);
await page.waitForTimeout(1500);
await page.screenshot({ path: out, fullPage: full === "1" });
if (errors.length) console.log("PAGE ERRORS:\n" + errors.join("\n"));
await browser.close();
server.close();
