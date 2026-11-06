// node --test (Node 22+ runs TypeScript directly); run via `make test`.
import assert from "node:assert/strict";
import { test } from "node:test";
import { clockTime, dayIn, dayLabel, groupTime } from "./format.ts";

const ET = "America/New_York";
const PT = "America/Los_Angeles";

test("clock time is the group's, not the viewer's", () => {
  const t = Date.parse("2026-11-04T20:13:00Z"); // 3:13 PM in New York (EST), 12:13 PM in LA
  assert.equal(clockTime(t, ET), "3:13 PM");
  assert.equal(clockTime(t, PT), "12:13 PM");
});

test("today's entries say Today", () => {
  const now = Date.parse("2026-11-04T23:00:00Z"); // 6 PM ET
  assert.equal(groupTime(Date.parse("2026-11-04T20:13:00Z"), ET, now), "Today, 3:13 PM");
});

test("older entries show the date", () => {
  const now = Date.parse("2026-11-05T15:00:00Z");
  assert.equal(groupTime(Date.parse("2026-11-04T20:13:00Z"), ET, now), "Nov 4, 3:13 PM");
});

test("'today' is the group's day: 02:00 UTC is still yesterday in New York", () => {
  const now = Date.parse("2026-11-05T15:00:00Z"); // Nov 5 in both zones
  const late = Date.parse("2026-11-05T02:30:00Z"); // Nov 4, 9:30 PM ET; Nov 4, 6:30 PM PT
  assert.equal(groupTime(late, ET, now), "Nov 4, 9:30 PM");
  assert.equal(dayIn(late, "UTC"), "2026-11-05");
  assert.equal(dayIn(late, ET), "2026-11-04");
});

test("daylight saving follows the zone", () => {
  // 15:00 UTC is 11 AM EDT in October, 10 AM EST in December.
  assert.equal(clockTime(Date.parse("2026-10-20T15:00:00Z"), ET), "11:00 AM");
  assert.equal(clockTime(Date.parse("2026-12-20T15:00:00Z"), ET), "10:00 AM");
});

test("another year shows the year", () => {
  const now = Date.parse("2027-01-02T15:00:00Z");
  assert.equal(groupTime(Date.parse("2026-12-31T20:00:00Z"), ET, now), "Dec 31, 2026, 3:00 PM");
});

test("day labels are calendar days, with no timezone shift", () => {
  assert.equal(dayLabel("2026-11-04"), "Wed, Nov 4");
});
