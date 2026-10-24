import assert from "node:assert/strict";
import http from "node:http";
import fs from "node:fs";
import { chromium } from "playwright";

const worker = fs.readFileSync(new URL("./service-worker.js", import.meta.url), "utf8");
const html = `<!doctype html><html><head><title>ZEIBAEL Browser Fixture</title></head>
<body><button id="increment">Increase</button><output id="counter">0</output>
<script>
document.querySelector("#increment").addEventListener("click", () => {
  const counter = document.querySelector("#counter");
  counter.textContent = String(Number(counter.textContent) + 1);
});
navigator.serviceWorker.register("/service-worker.js");
</script></body></html>`;
const server = http.createServer((req, res) => {
  if (req.url === "/service-worker.js") {
    res.writeHead(200, {"content-type": "text/javascript", "cache-control": "no-store"});
    return res.end(worker);
  }
  if (req.url === "/offline.html") {
    res.writeHead(200, {"content-type": "text/html"});
    return res.end("<h1>Offline</h1>");
  }
  if (req.url === "/") {
    res.writeHead(200, {"content-type": "text/html"});
    return res.end(html);
  }
  res.writeHead(404); res.end("Not Found");
});
await new Promise((resolve, reject) => {
  server.once("error", reject);
  server.listen(0, "127.0.0.1", resolve);
});
let browser;
try {
  const base = "http://127.0.0.1:" + server.address().port;
  browser = await chromium.launch({headless: true});
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(base, {waitUntil:"load"});
  await page.locator("#increment").click();
  assert.equal(await page.locator("#counter").textContent(), "1");
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload();
  await page.waitForFunction(() => navigator.serviceWorker.controller !== null);
  await context.setOffline(true);
  await page.reload({waitUntil:"domcontentloaded"});
  assert.equal(await page.title(), "ZEIBAEL Browser Fixture");
  assert.equal(await page.locator("#counter").textContent(), "0");
  console.log("PLAYWRIGHT_BROWSER_AND_PWA_OFFLINE_OK");
} finally {
  if (browser) await browser.close();
  await new Promise((resolve, reject) => server.close(e => e ? reject(e) : resolve()));
}
