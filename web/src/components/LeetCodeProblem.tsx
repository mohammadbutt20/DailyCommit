"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { LeetCodeAccount, useLeetCodeAccount } from "@/components/LeetCodeAccount";
import { Badge, Button, Difficulty, ErrorText, Eyebrow, Spinner } from "@/components/ui";
import { api, type Schemas, unwrap } from "@/lib/api/client";

type Problem = Schemas["ProblemDetail"];
type Group = Schemas["GroupDetail"];

/** Today's problem when it lives on LeetCode: read it here, solve it there, we verify. */
export function LeetCodeProblem({
  problem: p,
  group: g,
  userId,
}: {
  problem: Problem;
  group: Group;
  userId: number | undefined;
}) {
  return (
    <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,7fr)_minmax(0,4fr)]">
      <section className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-line bg-surface">
        <div className="border-b border-line px-6 py-5">
          <h1 className="text-2xl font-semibold tracking-tight">
            {p.frontend_id && <span className="text-faint">{p.frontend_id}. </span>}
            {p.title}
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Difficulty level={p.difficulty} />
            {p.topics.map((t) => (
              <Badge key={t}>{t.replaceAll("-", " ")}</Badge>
            ))}
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {/* Sanitized on import (backend leetcode/importer.py), so it's safe to render. */}
          <div
            className="markdown leetcode-statement text-[15px]"
            dangerouslySetInnerHTML={{ __html: p.statement_html ?? "" }}
          />
          <p className="mt-6 text-xs text-faint">
            Problem from{" "}
            <a href={p.source_url ?? "#"} target="_blank" rel="noopener noreferrer" className="hover:text-fg">
              LeetCode
            </a>
            .
          </p>
        </div>
      </section>
      <SolvePanel problem={p} group={g} userId={userId} />
    </div>
  );
}

function SolvePanel({ problem: p, group: g, userId }: { problem: Problem; group: Group; userId?: number }) {
  const queryClient = useQueryClient();
  const account = useLeetCodeAccount();
  const [note, setNote] = useState<string | null>(null);
  const me = g.members.find((m) => m.user_id === userId);
  const solved = me?.solved_today ?? false;

  const check = useMutation({
    mutationFn: () => unwrap(api.POST("/api/me/leetcode/check")),
    onSuccess: async (r) => {
      setNote(
        r.credited > 0
          ? null
          : "No accepted submission for this problem today yet. LeetCode can take a minute to show new ones.",
      );
      await queryClient.invalidateQueries({ queryKey: ["group", g.id] });
    },
  });

  return (
    <aside className="flex flex-col gap-4 overflow-y-auto">
      <div className="rounded-xl border border-line bg-surface p-5">
        <Eyebrow>Today&apos;s status</Eyebrow>
        <p className={`mt-2 text-lg font-semibold ${solved ? "text-accent" : "text-fg"}`}>
          {solved ? "✓ Solved. Streak safe from you." : "Not solved yet"}
        </p>
        {!solved && me && !me.eligible_today && (
          <p className="mt-1 text-xs text-faint">You joined today, so today doesn&apos;t count against the streak.</p>
        )}
        <a
          href={p.source_url ?? "#"}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-accent text-sm font-semibold text-[#06140d] transition-opacity hover:opacity-90"
        >
          Solve on LeetCode ↗
        </a>
        {account.data?.username && !solved && (
          <div className="mt-3">
            <Button
              variant="secondary"
              className="w-full"
              onClick={() => check.mutate()}
              disabled={check.isPending}
            >
              {check.isPending ? <Spinner /> : "I solved it, check now"}
            </Button>
            {note && <p className="mt-2 text-xs text-muted">{note}</p>}
            <ErrorText error={check.error} />
          </div>
        )}
        <p className="mt-4 text-xs leading-relaxed text-faint">
          Submit on leetcode.com. An <span className="text-muted">Accepted</span> submission made
          today ({g.timezone.replaceAll("_", " ")}) counts for the streak. We check automatically
          every few minutes.
        </p>
      </div>
      <div className="rounded-xl border border-line bg-surface p-5">
        <Eyebrow>LeetCode account</Eyebrow>
        <div className="mt-3">
          <LeetCodeAccount />
        </div>
      </div>
    </aside>
  );
}
