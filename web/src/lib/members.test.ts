import assert from "node:assert/strict";
import { test } from "node:test";
import { memberStatus } from "./members.ts";

const m = (paused: boolean, eligible_today: boolean, solved_today: boolean) => ({
  paused,
  eligible_today,
  solved_today,
});

test("joined today and already solved: no contradiction", () => {
  assert.deepEqual(memberStatus(m(false, false, true)), {
    text: "Solved · joins the streak tomorrow",
    badge: "solved",
  });
});

test("the other states", () => {
  assert.deepEqual(memberStatus(m(false, true, true)), { text: "Solved today", badge: "solved" });
  assert.deepEqual(memberStatus(m(false, true, false)), { text: "Hasn't solved yet", badge: "pending" });
  assert.deepEqual(memberStatus(m(false, false, false)), { text: "Joins the streak tomorrow", badge: null });
  assert.equal(memberStatus(m(true, false, true)).badge, "paused");
});
