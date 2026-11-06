export function duration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h) return `${h}h ${String(m).padStart(2, "0")}m`;
  if (m) return `${m}m`;
  return `${seconds}s`;
}

export function untilText(iso: string, now: number): string {
  const s = Math.max(0, Math.floor((new Date(iso).getTime() - now) / 1000));
  return duration(s);
}

/** "2026-10-22" + 1 day, in calendar terms (no timezone involved). */
export function nextDay(day: string): string {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

export const VERDICT_LABEL: Record<string, string> = {
  AC: "Accepted",
  WA: "Wrong answer",
  TLE: "Time limit exceeded",
  MLE: "Memory limit exceeded",
  RE: "Runtime error",
  CE: "Compile error",
  IE: "Internal error",
  skipped: "Skipped",
};

export function verdictColor(verdict: string | null | undefined): string {
  if (verdict === "AC") return "text-accent";
  if (verdict === "skipped" || !verdict) return "text-faint";
  if (verdict === "TLE" || verdict === "MLE") return "text-warn";
  return "text-danger";
}

/** Background + border classes for a verdict chip or banner. */
export function verdictSurface(verdict: string | null | undefined): string {
  if (verdict === "AC") return "border-[#3fd68f40] bg-accent-soft";
  if (verdict === "skipped" || !verdict) return "border-line bg-raised";
  if (verdict === "TLE" || verdict === "MLE") return "border-[#f2b84b40] bg-warn-soft";
  return "border-[#f0646f40] bg-danger-soft";
}

// Times are shown in the group's timezone (the one that defines its day), not the viewer's:
// "3:14 PM" means 3:14 PM on the group's clock, for everyone in the group.

/** "3:14 PM" in `timeZone`. */
export function clockTime(ms: number, timeZone?: string): string {
  return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone }).format(ms);
}

/** The calendar day of `ms` in `timeZone`, as "YYYY-MM-DD". */
export function dayIn(ms: number, timeZone?: string): string {
  // en-CA formats dates as YYYY-MM-DD.
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(ms);
}

/** "Today, 3:13 PM", or "Nov 4, 3:13 PM" (with the year if it isn't this year), in `timeZone`. */
export function groupTime(ms: number, timeZone: string, now: number = Date.now()): string {
  const time = clockTime(ms, timeZone);
  const day = dayIn(ms, timeZone);
  if (day === dayIn(now, timeZone)) return `Today, ${time}`;
  const sameYear = day.slice(0, 4) === dayIn(now, timeZone).slice(0, 4);
  const date = new Intl.DateTimeFormat("en-US", {
    timeZone,
    month: "short",
    day: "numeric",
    ...(sameYear ? {} : { year: "numeric" }),
  }).format(ms);
  return `${date}, ${time}`;
}

/** A calendar day "2026-11-04" as "Wed, Nov 4" (no timezone involved: it's already a day). */
export function dayLabel(day: string): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "UTC",
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(new Date(`${day}T12:00:00Z`));
}

/** "Nov 4, 2026, 3:13 PM" in the viewer's own timezone (their own submission history). */
export function localDateTime(iso: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}
