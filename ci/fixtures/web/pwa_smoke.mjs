import assert from "node:assert/strict";
import fs from "node:fs";
const manifest = JSON.parse(fs.readFileSync("ci/fixtures/web/manifest.webmanifest", "utf8"));
const worker = fs.readFileSync("ci/fixtures/web/service-worker.js", "utf8");
assert.equal(manifest.display, "standalone");
assert.ok(manifest.start_url.startsWith("/"));
assert.ok(worker.includes("install") && worker.includes("fetch"));
assert.ok(worker.includes("caches.match") && worker.includes("caches.open"));
console.log("PWA_STATIC_CONTRACT_SMOKE_OK");
