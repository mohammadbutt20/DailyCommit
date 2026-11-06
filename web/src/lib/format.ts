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

export function clockTime(ms: number): string {
  return new Date(ms).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

/** "Nov 5": for timestamps that aren't from today. */
export function shortDate(ms: number): string {
  return new Date(ms).toLocaleDateString([], { month: "short", day: "numeric" });
}
