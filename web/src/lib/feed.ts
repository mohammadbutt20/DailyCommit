// The group page's activity feed: history loaded from GET /api/groups/{id}/activity, plus
// live `solve` / `join` events from the `group:{id}` topic. Both carry the same server-built
// id (backend domain/activity.py), so an event that arrives both ways is shown once.
// Pure functions only: unit-tested with `node --test` (feed.test.ts).

import type { components } from "./api/schema";

type ActivityOut = components["schemas"]["ActivityOut"];

export type FeedItem = {
  id: string;
  kind: "solve" | "join";
  who: string;
  at: number; // epoch ms
  problem: string | null; // slug, solves only
};

export const FEED_LIMIT = 20;

export function fromHistory(a: ActivityOut): FeedItem {
  return {
    id: a.id,
    kind: a.kind,
    who: a.display_name,
    at: Date.parse(a.at),
    problem: a.problem_slug ?? null,
  };
}

/** A live message as a feed item, or null for events the feed doesn't show. */
export function fromLive(event: string, data: Record<string, unknown>, now = Date.now()): FeedItem | null {
  if (event !== "solve" && event !== "join") return null;
  const parsed = typeof data.at === "string" ? Date.parse(data.at) : NaN;
  const at = Number.isNaN(parsed) ? now : parsed;
  return {
    // Every server event has an id; the fallback only keeps an id-less event from merging
    // with an unrelated one.
    id: typeof data.id === "string" ? data.id : `${event}:${String(data.user_id)}:${at}`,
    kind: event,
    who: String(data.display_name ?? "Someone"),
    at,
    problem: typeof data.problem === "string" ? data.problem : null,
  };
}

/** Newest first, one entry per id, at most `limit`. Same order as the backend: (at, id) desc. */
export function mergeFeed(lists: FeedItem[][], limit = FEED_LIMIT): FeedItem[] {
  const byId = new Map<string, FeedItem>();
  for (const list of lists) for (const item of list) if (!byId.has(item.id)) byId.set(item.id, item);
  return [...byId.values()]
    .sort((a, b) => b.at - a.at || (a.id < b.id ? 1 : a.id > b.id ? -1 : 0))
    .slice(0, limit);
}

export function feedText(item: FeedItem): string {
  if (item.kind === "join") return "joined the group";
  return item.problem ? `solved ${item.problem}` : "solved the daily problem";
}

/** Whether `at` falls on the same local calendar day as `now` (show a time, not a date). */
export function isSameLocalDay(at: number, now: number): boolean {
  return new Date(at).toDateString() === new Date(now).toDateString();
}
