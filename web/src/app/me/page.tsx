"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Difficulty,
  Empty,
  ErrorText,
  Eyebrow,
  Loading,
  Skeleton,
  cx,
} from "@/components/ui";
import { api, type Schemas, unwrap } from "@/lib/api/client";
import { VERDICT_LABEL, localDateTime, verdictColor } from "@/lib/format";
import { useRequireMe } from "@/lib/queries";

const LANGUAGE_NAMES: Record<string, string> = { python: "Python", java: "Java", cpp: "C++" };

export default function MyHistoryPage() {
  const me = useRequireMe();
  const stats = useQuery({
    queryKey: ["me", "stats"],
    queryFn: () => unwrap(api.GET("/api/me/stats")),
    enabled: me.isSuccess,
  });
  const subs = useInfiniteQuery({
    queryKey: ["me", "submissions"],
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/me/submissions", {
          params: { query: { limit: 25, ...(pageParam ? { before_id: pageParam } : {}) } },
        }),
      ),
    initialPageParam: null as number | null,
    getNextPageParam: (last) => last.next_before_id,
    enabled: me.isSuccess,
  });

  if (!me.data) return <Loading />;
  const rows = subs.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="space-y-8">
      <div>
        <Eyebrow>My history</Eyebrow>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">{me.data.user.display_name}</h1>
        <p className="mt-1.5 text-muted">Your submissions and progress. Only you can see this page.</p>
      </div>

      {stats.isError ? <ErrorText error={stats.error} /> : <Stats stats={stats.data} />}

      <Card padded={false} className="overflow-hidden">
        <div className="px-5 pt-5">
          <CardHeader title="Submissions" hint="Newest first. Open one to see the code you sent." />
        </div>
        {subs.isError ? (
          <div className="px-5 pb-5">
            <ErrorText error={subs.error} />
          </div>
        ) : !subs.data ? (
          <div className="space-y-2 px-5 pb-5">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <div className="px-5 pb-5">
            <Empty>No submissions yet. Solve today&apos;s problem to get started.</Empty>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-y border-line bg-sunken/60 text-xs text-faint">
                <tr>
                  {["Problem", "Group", "Language", "Verdict", "Tests", "Runtime", "Submitted"].map(
                    (h) => (
                      <th key={h} className="px-5 py-2 font-medium">
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((s) => (
                  <SubmissionRow key={s.id} s={s} />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {subs.hasNextPage && (
          <div className="border-t border-line px-5 py-3 text-center">
            <Button
              variant="ghost"
              size="sm"
              disabled={subs.isFetchingNextPage}
              onClick={() => subs.fetchNextPage()}
            >
              {subs.isFetchingNextPage ? "Loading…" : "Load more"}
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}

function SubmissionRow({ s }: { s: Schemas["MySubmissionOut"] }) {
  const href = `/me/submissions/${s.id}`;
  const cell = "px-5 py-2.5";
  return (
    <tr className="transition-colors hover:bg-raised">
      <td className={cell}>
        <Link href={href} className="flex items-center gap-2 font-medium hover:text-accent">
          <span className="truncate">{s.problem_title}</span>
          <Difficulty level={s.difficulty} />
        </Link>
      </td>
      <td className={cx(cell, "text-muted")}>{s.group?.name ?? "—"}</td>
      <td className={cx(cell, "text-muted")}>
        {LANGUAGE_NAMES[s.language] ?? s.language}
        {s.kind !== "submit" && <span className="ml-1.5 text-xs text-faint">({s.kind})</span>}
      </td>
      <td className={cx(cell, "font-medium", verdictColor(s.verdict))}>
        <Link href={href}>
          {s.status === "done" ? (VERDICT_LABEL[s.verdict ?? ""] ?? s.verdict) : "Running…"}
        </Link>
      </td>
      <td className={cx(cell, "font-mono text-xs text-muted")}>
        {s.passed}/{s.total}
      </td>
      <td className={cx(cell, "font-mono text-xs text-muted")}>
        {s.runtime_ms != null ? `${s.runtime_ms} ms` : "—"}
      </td>
      <td className={cx(cell, "text-xs whitespace-nowrap text-muted")}>{localDateTime(s.created_at)}</td>
    </tr>
  );
}

function Stats({ stats: s }: { stats: Schemas["StatsOut"] | undefined }) {
  if (!s) {
    return (
      <div className="grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
    );
  }
  const rate = s.accepted_rate == null ? "—" : `${Math.round(s.accepted_rate * 100)}%`;
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card>
        <Eyebrow>Problems solved</Eyebrow>
        <p className="mt-2 font-mono text-3xl font-semibold text-accent">{s.problems_solved}</p>
        <p className="mt-1 text-xs text-faint">distinct problems, including practice</p>
      </Card>
      <Card>
        <Eyebrow>Accepted rate</Eyebrow>
        <p className="mt-2 font-mono text-3xl font-semibold">{rate}</p>
        <p className="mt-1 text-xs text-faint">
          {s.accepted} of {s.submissions} judged submissions (sample runs not counted)
        </p>
      </Card>
      <Card>
        <Eyebrow>Streaks</Eyebrow>
        {s.streaks.length === 0 ? (
          <p className="mt-2 text-sm text-faint">Join a group to start one.</p>
        ) : (
          <ul className="mt-2 space-y-1.5 text-sm">
            {s.streaks.map((g) => (
              <li key={g.group_id} className="flex items-center justify-between gap-3">
                <Link href={`/g/${g.group_id}`} className="truncate hover:text-accent">
                  {g.group_name}
                </Link>
                <span className="font-mono text-xs text-muted">
                  <span className="text-fg">{g.current_streak}</span> now · best {g.best_streak}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Breakdown title="Solved by language" counts={s.by_language} names={LANGUAGE_NAMES} />
      <Breakdown title="Solved by difficulty" counts={s.by_difficulty} difficulty />
    </div>
  );
}

function Breakdown({
  title,
  counts,
  names,
  difficulty,
}: {
  title: string;
  counts: Record<string, number>;
  names?: Record<string, string>;
  difficulty?: boolean;
}) {
  const entries = Object.entries(counts);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  return (
    <Card>
      <Eyebrow>{title}</Eyebrow>
      {entries.length === 0 ? (
        <p className="mt-2 text-sm text-faint">Nothing solved yet.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {entries.map(([key, n]) => (
            <li key={key} className="grid grid-cols-[5.5rem_minmax(0,1fr)_2rem] items-center gap-3 text-sm">
              {difficulty ? <Difficulty level={key} /> : <Badge>{names?.[key] ?? key}</Badge>}
              <span className="h-1.5 overflow-hidden rounded-full bg-line">
                <span
                  className="block h-full rounded-full bg-accent"
                  style={{ width: `${(100 * n) / max}%` }}
                />
              </span>
              <span className="text-right font-mono text-xs text-muted">{n}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
