"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
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
} from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";
import { useRequireMe } from "@/lib/queries";

export default function GroupsPage() {
  const me = useRequireMe();
  const router = useRouter();
  const [name, setName] = useState("");
  const [code, setCode] = useState("");

  const groups = useQuery({
    queryKey: ["groups"],
    queryFn: () => unwrap(api.GET("/api/groups")),
    enabled: me.isSuccess,
  });
  const create = useMutation({
    mutationFn: () => unwrap(api.POST("/api/groups", { body: { name } })),
    onSuccess: (g) => router.push(`/g/${g.id}`),
  });
  const join = useMutation({
    mutationFn: () => unwrap(api.POST("/api/groups/join", { body: { invite_code: code } })),
    onSuccess: (g) => router.push(`/g/${g.id}`),
  });

  if (!groups.data) return <Loading />;
  const todo = groups.data.filter((g) => g.today_problem && !g.solved_today).length;

  return (
    <div className="space-y-10">
      <div>
        <Eyebrow>Dashboard</Eyebrow>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">
          {me.data ? `Hey, ${me.data.user.display_name}` : "Your groups"}
        </h1>
        <p className="mt-1.5 text-muted">
          {groups.data.length === 0
            ? "Create a group or join one with an invite code to get started."
            : todo > 0
              ? `${todo} ${todo === 1 ? "problem" : "problems"} waiting for you today.`
              : "You're all caught up for today."}
        </p>
      </div>

      {groups.data.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {groups.data.map((g) => (
            <Link key={g.id} href={`/g/${g.id}`} className="group rounded-xl">
              <Card className="flex h-full flex-col transition-colors group-hover:border-line-strong group-hover:bg-[#12161b]">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="truncate text-base font-semibold tracking-tight">{g.name}</h2>
                    <p className="mt-0.5 text-xs text-muted">
                      {g.member_count} {g.member_count === 1 ? "member" : "members"}
                      {g.role === "leader" && " · you lead"}
                    </p>
                  </div>
                  <div className="text-right">
                    <p
                      className={`font-mono text-2xl leading-none font-semibold ${
                        g.current_streak > 0 ? "text-accent" : "text-faint"
                      }`}
                    >
                      {g.current_streak}
                    </p>
                    <p className="mt-1 text-[10px] tracking-wide text-faint uppercase">
                      day streak
                    </p>
                  </div>
                </div>

                <div className="mt-6 flex-1 rounded-lg border border-line bg-sunken p-3">
                  {g.today_problem ? (
                    <>
                      <div className="flex items-center justify-between gap-2">
                        <Eyebrow>Today</Eyebrow>
                        {g.solved_today ? (
                          <Badge tone="accent">✓ Solved</Badge>
                        ) : (
                          <Badge tone="warn">To do</Badge>
                        )}
                      </div>
                      <p className="mt-2 truncate text-sm font-medium">{g.today_problem.title}</p>
                      <div className="mt-2 flex items-center gap-2">
                        <Difficulty level={g.today_problem.difficulty} />
                        <span className="truncate text-xs text-faint">
                          {g.today_problem.topics.join(" · ")}
                        </span>
                      </div>
                    </>
                  ) : (
                    <p className="text-sm text-faint">No problem assigned yet</p>
                  )}
                </div>
                <p className="mt-4 text-xs text-faint transition-colors group-hover:text-accent">
                  Open group →
                </p>
              </Card>
            </Link>
          ))}
        </div>
      )}

      {groups.data.length === 0 && <Empty>You&apos;re not in any groups yet.</Empty>}

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader title="Create a group" hint="You'll be the leader and get an invite code." />
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate();
            }}
          >
            <Input placeholder="Group name" value={name} onChange={(e) => setName(e.target.value)} />
            <Button type="submit" disabled={!name.trim() || create.isPending}>
              Create
            </Button>
          </form>
          <ErrorText error={create.error} />
        </Card>
        <Card>
          <CardHeader title="Join a group" hint="Ask a member for their invite code." />
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              join.mutate();
            }}
          >
            <Input
              placeholder="e.g. DEMO2026"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              className="font-mono tracking-widest"
            />
            <Button
              variant="secondary"
              type="submit"
              disabled={code.trim().length < 4 || join.isPending}
            >
              Join
            </Button>
          </form>
          <ErrorText error={join.error} />
        </Card>
      </div>
    </div>
  );
}
