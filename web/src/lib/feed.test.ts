// node --test (Node 22+ runs TypeScript directly); run via `make test`.
import assert from "node:assert/strict";
import { test } from "node:test";
import { type FeedItem, feedText, fromHistory, fromLive, mergeFeed } from "./feed.ts";

const T = Date.parse("2026-11-05T12:00:00Z");

function item(id: string, minutesAgo: number, kind: FeedItem["kind"] = "solve"): FeedItem {
  return { id, kind, who: id, at: T - minutesAgo * 60_000, problem: null };
}

test("history converts to feed items", () => {
  const got = fromHistory({
    id: "solve:2026-11-05:4",
    kind: "solve",
    user_id: 4,
    display_name: "Bob",
    at: "2026-11-05T12:00:00Z",
    problem_slug: "two-sum",
  });
  assert.deepEqual(got, { id: "solve:2026-11-05:4", kind: "solve", who: "Bob", at: T, problem: "two-sum" });
});

test("live events use the server's id and time", () => {
  const got = fromLive("solve", {
    id: "solve:2026-11-05:4",
    user_id: 4,
    display_name: "Bob",
    problem: "two-sum",
    at: "2026-11-05T12:00:00+00:00",
  });
  assert.deepEqual(got, { id: "solve:2026-11-05:4", kind: "solve", who: "Bob", at: T, problem: "two-sum" });
});

test("live events the feed doesn't show are ignored", () => {
  assert.equal(fromLive("test", { id: "x" }), null);
});

test("a live event without id or time still gets a unique entry", () => {
  const got = fromLive("join", { user_id: 9, display_name: "Zed" }, T);
  assert.equal(got?.at, T);
  assert.equal(got?.id, `join:9:${T}`);
});

test("an event in both history and live is shown once", () => {
  const history = [item("solve:2026-11-05:4", 5), item("join:7", 60, "join")];
  const live = [item("solve:2026-11-05:4", 5), item("solve:2026-11-05:5", 1)];
  assert.deepEqual(
    mergeFeed([live, history]).map((i) => i.id),
    ["solve:2026-11-05:5", "solve:2026-11-05:4", "join:7"],
  );
});

test("live events land on top of the history, newest first", () => {
  const history = [item("a", 30), item("b", 10)]; // out of order on purpose
  const live = [item("c", 0)];
  assert.deepEqual(mergeFeed([live, history]).map((i) => i.id), ["c", "b", "a"]);
});

test("equal times order by id descending, like the backend", () => {
  assert.deepEqual(mergeFeed([[item("join:1", 0), item("join:2", 0)]]).map((i) => i.id), ["join:2", "join:1"]);
});

test("the feed is capped", () => {
  const many = Array.from({ length: 30 }, (_, n) => item(`e${n}`, n));
  const got = mergeFeed([many], 20);
  assert.equal(got.length, 20);
  assert.equal(got[0].id, "e0");
});

test("feed text", () => {
  assert.equal(feedText({ ...item("j", 0, "join") }), "joined the group");
  assert.equal(feedText({ ...item("s", 0), problem: "two-sum" }), "solved two-sum");
  assert.equal(feedText(item("s", 0)), "solved the daily problem");
});
