import assert from "node:assert/strict";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { chromium, firefox, webkit } from "playwright";

// Committed, public-safe localhost fixture. No user URL, cookie or token.
const browserName = process.argv[2];
const supported = { chromium, firefox, webkit };
if (!Object.hasOwn(supported, browserName)) {
  throw new Error("ZEIBAEL internal browser allowlist: chromium, firefox, webkit only");
}
const outputRoot = process.env.ZEIBAEL_OUTPUT_DIR;
if (!outputRoot) throw new Error("ZEIBAEL_OUTPUT_DIR is required");
const destination = path.join(outputRoot, "files", browserName + "-interaction.png");
const html = `<!doctype html><html lang="en"><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ZEIBAEL Browser Matrix</title>
<style>body{font-family:sans-serif;max-width:36rem;margin:2rem auto;padding:1rem}
button,input{font-size:1rem;padding:.6rem;margin:.4rem}output{font-weight:bold}</style>
</head><body>
<h1>ZEIBAEL Public Browser Fixture</h1>
<label for="name">Name</label><input id="name" type="text" />
<button id="greet">Greet</button><output id="greeting"></output>
<button id="increment">Increase</button><output id="counter">0</output>
<script>
document.querySelector("#increment").addEventListener("click",()=>{
const counter=document.querySelector("#counter");
counter.textContent=String(Number(counter.textContent)+1);
});
document.querySelector("#greet").addEventListener("click",()=>{
document.querySelector("#greeting").textContent=
"Hello, "+document.querySelector("#name").value;
});
</script></body></html>`;
const server = http.createServer((req, res) => {
  if (req.url === "/") {
    res.writeHead(200, { "content-type": "text/html; charset=utf-8",
                         "cache-control": "no-store" });
    res.end(html);
  } else {
    res.writeHead(404); res.end("Not found");
  }
});
await new Promise((resolve, reject) => {
  server.once("error", reject);
  server.listen(0, "127.0.0.1", resolve);
});
let browser;
try {
  const url = "http://127.0.0.1:" + server.address().port + "/";
  browser = await supported[browserName].launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    serviceWorkers: "block"
  });
  const page = await context.newPage();
  const response = await page.goto(url, { waitUntil: "load" });
  assert.equal(response.status(), 200);
  assert.equal(await page.title(), "ZEIBAEL Browser Matrix");
  await page.locator("#name").fill("Public Test");
  await page.locator("#greet").click();
  assert.equal(await page.locator("#greeting").textContent(), "Hello, Public Test");
  await page.locator("#increment").click();
  await page.locator("#increment").click();
  assert.equal(await page.locator("#counter").textContent(), "2");
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  await page.screenshot({ path: destination, fullPage: true });
  assert.ok(fs.statSync(destination).size > 1000);
  const signature = fs.readFileSync(destination).subarray(0, 8).toString("hex");
  assert.equal(signature, "89504e470d0a1a0a");
  console.log("BROWSER_MATRIX_" + browserName.toUpperCase() + "_OK screenshot=" + path.basename(destination));
  await context.close();
} finally {
  if (browser) await browser.close();
  await new Promise((resolve, reject) =>
    server.close(error => error ? reject(error) : resolve()));
}
