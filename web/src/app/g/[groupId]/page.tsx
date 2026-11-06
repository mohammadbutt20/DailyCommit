"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import StreakGraph from "@/components/StreakGraph";
import {
  Avatar,
  Badge,
  Button,
  Card,
  CardHeader,
  Difficulty,
  Empty,
  ErrorText,
  Eyebrow,
  Input,
  Loading,
  Segmented,
  Select,
  Spinner,
  cx,
} from "@/components/ui";
import { api, type Schemas, unwrap } from "@/lib/api/client";
import { type FeedItem, feedText, fromHistory, fromLive, isSameLocalDay, mergeFeed } from "@/lib/feed";
import { clockTime, duration, nextDay, shortDate, untilText } from "@/lib/format";
import { useGroup, useRequireMe } from "@/lib/queries";
import { useTopic } from "@/lib/ws";

type Group = Schemas["GroupDetail"];

export default function GroupPage() {
  const groupId = Number(useParams<{ groupId: string }>().groupId);
  const me = useRequireMe();
  const group = useGroup(groupId);
  const queryClient = useQueryClient();
  // The feed = history from the database + live events on top, deduplicated by event id, so
  // it survives a refresh and an event that arrives both ways shows once.
  const history = useQuery({
    queryKey: ["activity", groupId],
    queryFn: () =>
      unwrap(api.GET("/api/groups/{group_id}/activity", { params: { path: { group_id: groupId } } })),
    enabled: me.isSuccess,
  });
  const [live, setLive] = useState<{ groupId: number; items: FeedItem[] }>({ groupId, items: [] });
  const liveItems = live.groupId === groupId ? live.items : [];
  const feed = mergeFeed([liveItems, (history.data ?? []).map(fromHistory)]);

  useTopic(me.isSuccess ? `group:${groupId}` : null, (msg) => {
    const item = fromLive(msg.event, msg.data);
    if (item)
      setLive((l) => ({ groupId, items: mergeFeed([[item], l.groupId === groupId ? l.items : []]) }));
    queryClient.invalidateQueries({ queryKey: ["group", groupId] });
    queryClient.invalidateQueries({ queryKey: ["leaderboard", groupId] });
  });

  if (group.isError) return <ErrorText error={group.error} />;
  if (!group.data) return <Loading />;
  const g = group.data;
  const isLeader = g.my_role === "leader";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <Link href="/groups" className="text-xs text-faint transition-colors hover:text-fg">
            ← All groups
          </Link>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">{g.name}</h1>
          <div className="mt-3 flex items-center gap-6">
            <Stat
              label="Current streak"
              value={g.current_streak}
              unit="days"
              highlight={g.current_streak > 0}
            />
            <div className="h-8 w-px bg-line" />
            <Stat label="Best" value={g.best_streak} unit="days" />
            <div className="h-8 w-px bg-line" />
            <Stat label="Members" value={g.members.length} />
          </div>
        </div>
        <div className="w-full rounded-xl border border-line bg-surface p-4 sm:w-auto">
          <StreakGraph days={g.recent_days} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <TodayCard group={g} />
          <Members group={g} isLeader={isLeader} />
        </div>
        <div className="space-y-6">
          <Leaderboard groupId={groupId} />
          <Card>
            <CardHeader
              title={
                <span className="flex items-center gap-2">
                  <span className="animate-pulse-dot h-1.5 w-1.5 rounded-full bg-accent" />
                  Live activity
                </span>
              }
            />
            {feed.length === 0 ? (
              history.isPending ? (
                <Empty>Loading activity…</Empty>
              ) : history.isError ? (
                <ErrorText error={history.error} />
              ) : (
                <Empty>Solves and joins show up here as they happen.</Empty>
              )
            ) : (
              <ul className="space-y-3">
                {feed.map((item) => (
                  <li key={item.id} className="flex items-center gap-3 text-sm">
                    <Avatar name={item.who} size="sm" />
                    <span className="min-w-0 flex-1">
                      <span className="font-medium">{item.who}</span>{" "}
                      <span className={item.kind === "solve" ? "text-accent" : "text-muted"}>
                        {feedText(item)}
                      </span>
                    </span>
                    <span className="font-mono text-[11px] text-faint">
                      {isSameLocalDay(item.at, Date.now()) ? clockTime(item.at) : shortDate(item.at)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Invite group={g} isLeader={isLeader} />
          {isLeader && <TomorrowPicker group={g} />}
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  unit,
  highlight,
}: {
  label: string;
  value: number;
  unit?: string;
  highlight?: boolean;
}) {
  return (
    <div>
      <p className="text-[11px] tracking-wide text-faint uppercase">{label}</p>
      <p className="mt-0.5 font-mono text-xl font-semibold">
        <span className={highlight ? "text-accent" : "text-fg"}>{value}</span>
        {unit && <span className="ml-1 text-xs font-normal text-faint">{unit}</span>}
      </p>
    </div>
  );
}

function useNow(intervalMs = 30_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

function TodayCard({ group: g }: { group: Group }) {
  const now = useNow();
  const required = g.members.filter((m) => m.eligible_today);
  const done = required.filter((m) => m.solved_today).length;
  const pct = required.length ? (100 * done) / required.length : 0;
  const allDone = required.length > 0 && done === required.length;
  return (
    <Card padded={false} className="overflow-hidden">
      <div className="relative p-6">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,#3fd68f14,transparent_60%)]"
        />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <Eyebrow>Today · {g.today}</Eyebrow>
            {g.today_problem ? (
              <>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight">
                  {g.today_problem.title}
                </h2>
                <div className="mt-2.5 flex flex-wrap items-center gap-2">
                  <Difficulty level={g.today_problem.difficulty} />
                  {g.today_problem.topics.map((t) => (
                    <Badge key={t}>{t}</Badge>
                  ))}
                </div>
              </>
            ) : (
              <h2 className="mt-2 text-xl text-muted">No problem yet. Sync problems first.</h2>
            )}
          </div>
          {g.today_problem && (
            <Link href={`/g/${g.id}/today`}>
              <Button className="h-10 px-5">Solve now →</Button>
            </Link>
          )}
        </div>
      </div>
      <div className="border-t border-line bg-sunken/60 px-6 py-4">
        <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2 text-sm">
          <span className="text-muted">
            <span className={cx("font-mono font-semibold", allDone ? "text-accent" : "text-fg")}>
              {done}/{required.length}
            </span>{" "}
            required members solved
          </span>
          <span className="font-mono text-xs text-faint">
            day ends in <span className="text-muted">{untilText(g.day_ends_at, now)}</span>
            <span className="text-faint"> ({g.timezone.replaceAll("_", " ")})</span>
          </span>
        </div>
        <div className="flex gap-1">
          {required.length === 0 ? (
            <div className="h-1.5 flex-1 rounded-full bg-line" />
          ) : (
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-line">
              <div
                className="h-full rounded-full bg-accent transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

function Members({ group: g, isLeader }: { group: Group; isLeader: boolean }) {
  const queryClient = useQueryClient();
  const pause = useMutation({
    mutationFn: ({ userId, paused }: { userId: number; paused: boolean }) =>
      unwrap(
        api.PATCH("/api/groups/{group_id}/members/{user_id}", {
          params: { path: { group_id: g.id, user_id: userId } },
          body: { paused },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["group", g.id] }),
  });
  return (
    <Card>
      <CardHeader title="Members" hint={`${g.members.length} in this group`} />
      <ul className="-mx-2">
        {g.members.map((m) => (
          <li
            key={m.user_id}
            className="flex items-center justify-between gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-raised"
          >
            <div className="flex min-w-0 items-center gap-3">
              <Avatar
                name={m.display_name}
                src={m.avatar_url}
                ring={m.solved_today ? "accent" : "none"}
              />
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-sm font-medium">
                  <span className="truncate">{m.display_name}</span>
                  {m.role === "leader" && <Badge>leader</Badge>}
                </p>
                <p className="mt-0.5 text-xs text-faint">
                  {m.paused
                    ? "Paused, not counted toward the streak"
                    : !m.eligible_today
                      ? "Counts from tomorrow"
                      : m.solved_today
                        ? "Solved today"
                        : "Hasn't solved yet"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {m.paused ? (
                <Badge tone="warn">paused</Badge>
              ) : m.solved_today ? (
                <Badge tone="accent">✓ solved</Badge>
              ) : m.eligible_today ? (
                <Badge>pending</Badge>
              ) : null}
              {isLeader && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => pause.mutate({ userId: m.user_id, paused: !m.paused })}
                >
                  {m.paused ? "Unpause" : "Pause"}
                </Button>
              )}
            </div>
          </li>
        ))}
      </ul>
      <ErrorText error={pause.error} />
    </Card>
  );
}

const RANK_STYLES = [
  "bg-[#f5cf5b1f] text-gold border-[#f5cf5b40]",
  "bg-[#c9d1dc14] text-[#c9d1dc] border-[#c9d1dc30]",
  "bg-[#e0a37a14] text-[#e0a37a] border-[#e0a37a30]",
];

function Leaderboard({ groupId }: { groupId: number }) {
  const [period, setPeriod] = useState<"day" | "week">("day");
  const board = useQuery({
    queryKey: ["leaderboard", groupId, period],
    queryFn: () =>
      unwrap(
        api.GET("/api/groups/{group_id}/leaderboard", {
          params: { path: { group_id: groupId }, query: { period } },
        }),
      ),
  });
  return (
    <Card>
      <CardHeader
        title="Leaderboard"
        action={
          <Segmented
            value={period}
            onChange={setPeriod}
            options={[
              { value: "day", label: "Today" },
              { value: "week", label: "Week" },
            ]}
          />
        }
      />
      {!board.data ? (
        <Loading />
      ) : board.data.entries.length === 0 ? (
        <Empty>No solves yet. First one takes the top spot.</Empty>
      ) : (
        <ol className="space-y-1.5">
          {board.data.entries.map((e) => (
            <li
              key={e.user_id}
              className={cx(
                "flex items-center gap-3 rounded-lg px-2 py-2",
                e.rank === 1 && "bg-[#f5cf5b0a]",
              )}
            >
              <span
                className={cx(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-md border font-mono text-xs font-semibold",
                  RANK_STYLES[e.rank - 1] ?? "border-line text-faint",
                )}
              >
                {e.rank}
              </span>
              <Avatar name={e.display_name} size="sm" />
              <span className="min-w-0 flex-1 truncate text-sm">{e.display_name}</span>
              <span className="text-right font-mono text-xs text-muted">
                {period === "week" && <span className="text-fg">{e.solved} · </span>}
                {duration(e.seconds)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

function Invite({ group: g, isLeader }: { group: Group; isLeader: boolean }) {
  const queryClient = useQueryClient();
  const [copied, setCopied] = useState(false);
  const rotate = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/groups/{group_id}/invite/rotate", { params: { path: { group_id: g.id } } }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["group", g.id] }),
  });
  const link = typeof window === "undefined" ? "" : `${window.location.origin}/join/${g.invite_code}`;
  return (
    <Card>
      <CardHeader title="Invite friends" hint="Share the code or send the link." />
      <div className="flex items-center justify-between gap-2 rounded-lg border border-dashed border-line-strong bg-sunken px-4 py-3">
        <span className="font-mono text-lg font-semibold tracking-[0.25em]">{g.invite_code}</span>
        <Button
          variant={copied ? "secondary" : "primary"}
          size="sm"
          onClick={async () => {
            await navigator.clipboard.writeText(link);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          }}
        >
          {copied ? "✓ Copied" : "Copy link"}
        </Button>
      </div>
      {isLeader && (
        <Button
          variant="ghost"
          size="sm"
          className="mt-2 -ml-2"
          onClick={() => rotate.mutate()}
          disabled={rotate.isPending}
        >
          ↻ Generate new code
        </Button>
      )}
    </Card>
  );
}

function TomorrowPicker({ group: g }: { group: Group }) {
  const queryClient = useQueryClient();
  const problems = useQuery({
    queryKey: ["problems"],
    queryFn: () => unwrap(api.GET("/api/problems")),
  });
  const tomorrow = nextDay(g.today);
  const [link, setLink] = useState("");
  const set = useMutation({
    mutationFn: (slug: string) =>
      unwrap(
        api.PUT("/api/groups/{group_id}/daily/{day}", {
          params: { path: { group_id: g.id, day: tomorrow } },
          body: { problem_slug: slug },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["group", g.id] }),
  });
  return (
    <Card>
      <CardHeader title="Tomorrow's problem" hint={`Leader only · ${tomorrow}`} />
      <p className="mb-3 text-sm">
        {g.tomorrow_problem ? (
          <span className="font-medium">{g.tomorrow_problem.title}</span>
        ) : (
          <span className="text-muted">Picked automatically at midnight.</span>
        )}
      </p>
      <Select value="" onChange={(e) => e.target.value && set.mutate(e.target.value)}>
        <option value="">{g.tomorrow_problem ? "Change problem…" : "Choose a problem…"}</option>
        {problems.data?.map((p) => (
          <option key={p.slug} value={p.slug}>
            {p.frontend_id ? `${p.frontend_id}. ` : ""}
            {p.title} ({p.difficulty})
          </option>
        ))}
      </Select>
      <form
        className="mt-2 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (link.trim()) set.mutate(link.trim(), { onSuccess: () => setLink("") });
        }}
      >
        <Input
          placeholder="…or paste any LeetCode problem link"
          value={link}
          onChange={(e) => setLink(e.target.value)}
        />
        <Button type="submit" variant="secondary" disabled={!link.trim() || set.isPending}>
          {set.isPending ? <Spinner /> : "Set"}
        </Button>
      </form>
      <ErrorText error={set.error} />
    </Card>
  );
}
