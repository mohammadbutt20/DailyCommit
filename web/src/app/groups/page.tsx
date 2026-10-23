"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, ErrorText, Input, Loading } from "@/components/ui";
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

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">Your groups</h1>
      {groups.data.length === 0 ? (
        <p className="text-slate-400">You're not in a group yet. Create one or join with a code.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {groups.data.map((g) => (
            <Link key={g.id} href={`/g/${g.id}`}>
              <Card className="h-full transition hover:border-emerald-600">
                <div className="flex items-start justify-between">
                  <h2 className="text-lg font-semibold">{g.name}</h2>
                  <span className="font-mono text-emerald-400">{g.current_streak}d</span>
                </div>
                <p className="mt-1 text-sm text-slate-400">
                  {g.member_count} members · {g.role}
                </p>
                <p className="mt-4 text-sm">
                  {g.today_problem ? (
                    <>
                      Today: <span className="text-slate-200">{g.today_problem.title}</span>{" "}
                      {g.solved_today ? (
                        <span className="text-emerald-400">solved</span>
                      ) : (
                        <span className="text-amber-400">to do</span>
                      )}
                    </>
                  ) : (
                    <span className="text-slate-500">No problem assigned yet</span>
                  )}
                </p>
              </Card>
            </Link>
          ))}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <h2 className="mb-3 font-semibold">Create a group</h2>
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
          <h2 className="mb-3 font-semibold">Join with an invite code</h2>
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
            />
            <Button type="submit" disabled={code.trim().length < 4 || join.isPending}>
              Join
            </Button>
          </form>
          <ErrorText error={join.error} />
        </Card>
      </div>
    </div>
  );
}
