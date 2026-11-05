import type { Schemas } from "@/lib/api/client";
import { cx } from "./ui";

type Day = Schemas["GroupDetail"]["recent_days"][number];

function shortDate(day: string): string {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** The group's recent days as a contribution strip: kept, missed, or still in progress. */
export default function StreakGraph({ days }: { days: Day[] }) {
  const ordered = [...days].reverse(); // API is newest first
  if (ordered.length === 0) return null;
  return (
    <div>
      <div className="flex gap-[5px]">
        {ordered.map((d, i) => {
          const isToday = i === ordered.length - 1;
          const ratio = d.eligible_count ? d.solved_count / d.eligible_count : 0;
          return (
            <div
              key={d.day}
              title={`${shortDate(d.day)}: ${d.solved_count}/${d.eligible_count} solved${
                d.kept === null ? " (in progress)" : d.kept ? ", streak kept" : ", streak broken"
              }`}
              className={cx(
                "relative aspect-square max-w-7 min-w-0 flex-1 basis-0 rounded-[5px] border transition-transform hover:scale-110 sm:w-7 sm:flex-none",
                d.kept === true && "border-[#3fd68f55] bg-accent",
                d.kept === false && "border-[#f0646f30] bg-cell-miss",
                d.kept === null && "border-dashed border-line-strong bg-cell-empty",
                isToday && "ring-1 ring-fg/40 ring-offset-2 ring-offset-surface",
              )}
            >
              {d.kept === null && ratio > 0 && (
                <span
                  className="absolute inset-x-0 bottom-0 rounded-b-[4px] bg-accent/60"
                  style={{ height: `${ratio * 100}%` }}
                />
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex items-center justify-between gap-2 font-mono text-[10px] text-faint">
        <span>{shortDate(ordered[0]!.day)}</span>
        <span className="flex items-center gap-3">
          <Legend className="bg-accent" label="kept" />
          <Legend className="bg-cell-miss" label="missed" />
          <Legend
            className="border border-dashed border-line-strong bg-cell-empty"
            label="in progress"
          />
        </span>
        <span>today</span>
      </div>
    </div>
  );
}

function Legend({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className={cx("h-2 w-2 rounded-[2px]", className)} />
      {label}
    </span>
  );
}
