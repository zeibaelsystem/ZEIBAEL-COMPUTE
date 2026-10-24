import assert from "node:assert/strict";
type Job = { id: string; amount: number };
function sum(jobs: Job[]): number {
  return jobs.reduce((value, job) => value + job.amount, 0);
}
assert.equal(sum([{id: "first", amount: 2}, {id: "second", amount: 3}]), 5);
console.log("TYPESCRIPT_NODE_STRIP_TYPES_OK");
