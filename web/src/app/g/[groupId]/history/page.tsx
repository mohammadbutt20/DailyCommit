"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Badge, Card, Difficulty, Empty, ErrorText, Eyebrow, Loading, cx } from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";
import { dayLabel } from "@/lib/format";
import { useGroup, useRequireMe } from "@/lib/queries";

export default function HistoryPage() {
  const groupId = Number(useParams<{ groupId: string }>().groupId);
  const me = useRequireMe();
  const group = useGroup(groupId);
  const history = useQuery({
    queryKey: ["history", groupId],
    queryFn: () =>
      unwrap(api.GET("/api/groups/{group_id}/history", { params: { path: { group_id: groupId } } })),
    enabled: me.isSuccess,
  });

  if (group.isError) return <ErrorText error={group.error} />;
  if (history.isError) return <ErrorText error={history.error} />;
  if (!history.data || !group.data) return <Loading />;
  const days = history.data;
  const mine = days.filter((d) => d.solved_by_me).length;

  return (
    <div className="space-y-6">
      <div>
        <Link href={`/g/${groupId}`} className="text-xs text-faint transition-colors hover:text-fg">
          ← {group.data.name}
        </Link>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Past problems</h1>
        <p className="mt-1.5 text-muted">
          Every daily problem so far. You solved {mine} of {days.length}. Open one to practice it;
          practice never changes a streak or a day&apos;s results.
        </p>
      </div>

      {days.length === 0 ? (
        <Empty>No daily problems yet.</Empty>
      ) : (
        <Card padded={false} className="overflow-hidden">
          <ul className="divide-y divide-line">
            {days.map((d) => (
              <li key={d.day}>
                <Link
                  href={d.is_today ? `/g/${groupId}/today` : `/g/${groupId}/history/${d.day}`}
                  className="grid grid-cols-[7.5rem_minmax(0,1fr)_auto] items-center gap-4 px-5 py-3.5 transition-colors hover:bg-raised"
                >
                  <span className="font-mono text-xs text-muted">
                    {d.is_today ? (
                      <span className="text-accent">Today</span>
                    ) : (
                      dayLabel(d.day)
                    )}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{d.problem.title}</span>
                    <span className="mt-1 flex flex-wrap items-center gap-1.5">
                      <Difficulty level={d.problem.difficulty} />
                      {d.problem.topics.slice(0, 4).map((t) => (
                        <Badge key={t}>{t.replaceAll("-", " ")}</Badge>
                      ))}
                    </span>
                  </span>
                  <span className="flex items-center gap-3 text-right">
                    <span className="font-mono text-xs text-muted" title="Members who solved it that day">
                      <span className="text-fg">{d.solved_count}</span>/{d.member_count} solved
                    </span>
                    <span
                      className={cx(
                        "w-[4.75rem] rounded-md border px-2 py-0.5 text-center font-mono text-[11px] whitespace-nowrap",
                        d.solved_by_me
                          ? "border-[#3fd68f40] bg-accent-soft text-accent"
                          : "border-line text-faint",
                      )}
                    >
                      {d.solved_by_me ? "✓ you" : "not you"}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <Eyebrow>Times and days are in {group.data.timezone_label}</Eyebrow>
    </div>
  );
}
