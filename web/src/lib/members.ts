// What the members list says about each member today, kept in one place so the text and the
// badge never disagree (e.g. no "Counts from tomorrow" next to a "solved" badge).

export type MemberToday = {
  paused: boolean;
  eligible_today: boolean; // joined before today started (and not paused): counts today
  solved_today: boolean;
};

export type MemberStatus = {
  text: string;
  badge: "solved" | "pending" | "paused" | null;
};

export function memberStatus(m: MemberToday): MemberStatus {
  if (m.paused) return { text: "Paused, not counted toward the streak", badge: "paused" };
  if (m.solved_today) {
    return m.eligible_today
      ? { text: "Solved today", badge: "solved" }
      : { text: "Solved · joins the streak tomorrow", badge: "solved" };
  }
  if (!m.eligible_today) return { text: "Joins the streak tomorrow", badge: null };
  return { text: "Hasn't solved yet", badge: "pending" };
}
