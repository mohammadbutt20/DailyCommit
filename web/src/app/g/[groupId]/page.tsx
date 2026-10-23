"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, Card, ErrorText, Loading } from "@/components/ui";
import { api, type Schemas, unwrap } from "@/lib/api/client";
import { duration, nextDay, untilText } from "@/lib/format";
import { useGroup, useRequireMe } from "@/lib/queries";
import { useTopic } from "@/lib/ws";

type Group = Schemas["GroupDetail"];

export default function GroupPage() {
  const groupId = Number(useParams<{ groupId: string }>().groupId);
  const me = useRequireMe();
  const group = useGroup(groupId);
  const queryClient = useQueryClient();
  const [feed, setFeed] = useState<string[]>([]);

  useTopic(me.isSuccess ? `group:${groupId}` : null, (msg) => {
    const who = String(msg.data.display_name ?? "Someone");
    if (msg.event === "solve") setFeed((f) => [`${who} solved today's problem`, ...f].slice(0, 20));
    if (msg.event === "join") setFeed((f) => [`${who} joined the group`, ...f].slice(0, 20));
    queryClient.invalidateQueries({ queryKey: ["group", groupId] });
    queryClient.invalidateQueries({ queryKey: ["leaderboard", groupId] });
  });

  if (group.isError) return <ErrorText error={group.error} />;
  if (!group.data) return <Loading />;
  const g = group.data;
  const isLeader = g.my_role === "leader";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">{g.name}</h1>
          <p className="mt-1 text-slate-400">
            Group streak <span className="font-mono text-emerald-400">{g.current_streak}</span> ·
            best <span className="font-mono">{g.best_streak}</span>
          </p>
        </div>
        <StreakStrip days={g.recent_days} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <TodayCard group={g} />
          <Members group={g} isLeader={isLeader} />
        </div>
        <div className="space-y-6">
          <Leaderboard groupId={groupId} />
          <Card>
            <h2 className="mb-3 font-semibold">Live activity</h2>
            {feed.length === 0 ? (
              <p className="text-sm text-slate-500">Solves and joins show up here as they happen.</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {feed.map((item, i) => (
                  <li key={`${i}-${item}`}>{item}</li>
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
  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Today · {g.today}</p>
          {g.today_problem ? (
            <>
              <h2 className="mt-1 text-xl font-semibold">{g.today_problem.title}</h2>
              <p className="mt-1 text-sm text-slate-400">
                {g.today_problem.difficulty} · {g.today_problem.topics.join(", ")}
              </p>
            </>
          ) : (
            <h2 className="mt-1 text-xl text-slate-400">No problem yet. Sync problems first.</h2>
          )}
        </div>
        {g.today_problem && (
          <Link href={`/g/${g.id}/today`}>
            <Button>Solve</Button>
          </Link>
        )}
      </div>
      <div className="mt-5">
        <div className="mb-1 flex justify-between text-sm text-slate-400">
          <span>
            {done}/{required.length} required members solved
          </span>
          <span>day ends in {untilText(g.day_ends_at, now)}</span>
        </div>
        <div className="h-2 overflow-hidden rounded bg-slate-800">
          <div
            className="h-full bg-emerald-500 transition-all"
            style={{ width: `${required.length ? (100 * done) / required.length : 0}%` }}
          />
        </div>
      </div>
    </Card>
  );
}

function StreakStrip({ days }: { days: Group["recent_days"] }) {
  const ordered = [...days].reverse();
  return (
    <div className="flex gap-1" title="Recent days, oldest first">
      {ordered.map((d) => (
        <div
          key={d.day}
          title={`${d.day}: ${d.solved_count}/${d.eligible_count}`}
          className={`h-6 w-6 rounded ${
            d.kept === null ? "bg-slate-700" : d.kept ? "bg-emerald-500" : "bg-rose-500/70"
          }`}
        />
      ))}
    </div>
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
      <h2 className="mb-3 font-semibold">Members</h2>
      <ul className="divide-y divide-slate-800">
        {g.members.map((m) => (
          <li key={m.user_id} className="flex items-center justify-between py-2 text-sm">
            <span>
              <span className={m.solved_today ? "text-emerald-400" : "text-slate-500"}>
                {m.solved_today ? "●" : "○"}
              </span>{" "}
              {m.display_name}
              {m.role === "leader" && <span className="ml-2 text-xs text-slate-500">leader</span>}
              {m.paused && <span className="ml-2 text-xs text-amber-400">paused</span>}
              {!m.paused && !m.eligible_today && (
                <span className="ml-2 text-xs text-slate-500">counts from tomorrow</span>
              )}
            </span>
            {isLeader && (
              <button
                className="text-xs text-slate-400 hover:text-slate-100"
                onClick={() => pause.mutate({ userId: m.user_id, paused: !m.paused })}
              >
                {m.paused ? "Unpause" : "Pause"}
              </button>
            )}
          </li>
        ))}
      </ul>
      <ErrorText error={pause.error} />
    </Card>
  );
}

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
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold">Leaderboard</h2>
        <div className="flex gap-1 text-xs">
          {(["day", "week"] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`rounded px-2 py-1 ${period === p ? "bg-slate-700" : "text-slate-400"}`}
            >
              {p === "day" ? "Today" : "This week"}
            </button>
          ))}
        </div>
      </div>
      {!board.data ? (
        <Loading />
      ) : board.data.entries.length === 0 ? (
        <p className="text-sm text-slate-500">No solves yet.</p>
      ) : (
        <ol className="space-y-1 text-sm">
          {board.data.entries.map((e) => (
            <li key={e.user_id} className="flex justify-between">
              <span>
                <span className="mr-2 font-mono text-slate-500">{e.rank}.</span>
                {e.display_name}
              </span>
              <span className="font-mono text-slate-400">
                {period === "week" ? `${e.solved} solved · ` : ""}
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
      <h2 className="mb-2 font-semibold">Invite</h2>
      <p className="font-mono text-lg tracking-widest">{g.invite_code}</p>
      <div className="mt-3 flex gap-2">
        <Button
          variant="secondary"
          onClick={async () => {
            await navigator.clipboard.writeText(link);
            setCopied(true);
          }}
        >
          {copied ? "Copied" : "Copy link"}
        </Button>
        {isLeader && (
          <Button variant="secondary" onClick={() => rotate.mutate()} disabled={rotate.isPending}>
            New code
          </Button>
        )}
      </div>
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
      <h2 className="mb-2 font-semibold">Tomorrow&apos;s problem</h2>
      <p className="mb-3 text-sm text-slate-400">
        {g.tomorrow_problem ? g.tomorrow_problem.title : "Picked automatically at midnight."}
      </p>
      <select
        className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
        value=""
        onChange={(e) => e.target.value && set.mutate(e.target.value)}
      >
        <option value="">Choose a problem…</option>
        {problems.data?.map((p) => (
          <option key={p.slug} value={p.slug}>
            {p.title} ({p.difficulty})
          </option>
        ))}
      </select>
      <ErrorText error={set.error} />
    </Card>
  );
}
