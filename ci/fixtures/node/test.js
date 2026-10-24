const test = require("node:test");
const assert = require("node:assert/strict");
test("npm runs actual Node test", () => assert.equal(2 + 2, 4));
