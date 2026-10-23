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
  if (verdict === "AC") return "text-emerald-400";
  if (verdict === "skipped" || !verdict) return "text-slate-500";
  return "text-rose-400";
}
