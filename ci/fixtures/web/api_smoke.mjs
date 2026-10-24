import assert from "node:assert/strict";
import http from "node:http";

const server = http.createServer((req, res) => {
  if (req.method === "GET" && req.url === "/api/health") {
    res.writeHead(200, {"content-type": "application/json"});
    return res.end(JSON.stringify({ok: true}));
  }
  res.writeHead(404); res.end("Not Found");
});
await new Promise((resolve, reject) => {
  server.once("error", reject);
  server.listen(0, "127.0.0.1", resolve);
});
try {
  const url = "http://127.0.0.1:" + server.address().port;
  const res = await fetch(url + "/api/health");
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), {ok: true});
  assert.equal((await fetch(url + "/no-match")).status, 404);
  console.log("API_HTTP_SMOKE_OK");
} finally {
  await new Promise((resolve, reject) => server.close(e => e ? reject(e) : resolve()));
}
