import assert from "node:assert/strict";
import { test } from "node:test";
import { shouldRetry } from "./retry.ts";

test("client errors are not retried", () => {
  for (const status of [400, 401, 403, 404, 422, 429]) assert.equal(shouldRetry(0, { status }), false);
});

test("server and network errors are retried up to 3 times", () => {
  assert.equal(shouldRetry(0, { status: 502 }), true);
  assert.equal(shouldRetry(2, new TypeError("Failed to fetch")), true);
  assert.equal(shouldRetry(3, { status: 500 }), false);
});
