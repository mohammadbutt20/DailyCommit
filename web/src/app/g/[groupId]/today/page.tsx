"use client";

import Editor from "@monaco-editor/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Button, Card, ErrorText, Loading } from "@/components/ui";
import { api, type Schemas, unwrap } from "@/lib/api/client";
import { VERDICT_LABEL, verdictColor } from "@/lib/format";
import { useGroup, useRequireMe } from "@/lib/queries";
import { useTopic } from "@/lib/ws";

type Problem = Schemas["ProblemDetail"];

export default function TodayPage() {
  const groupId = Number(useParams<{ groupId: string }>().groupId);
  useRequireMe();
  const group = useGroup(groupId);
  const slug = group.data?.today_problem?.slug;
  const problem = useQuery({
    queryKey: ["problem", slug],
    queryFn: () => unwrap(api.GET("/api/problems/{slug}", { params: { path: { slug: slug! } } })),
    enabled: !!slug,
  });

  if (group.isError) return <ErrorText error={group.error} />;
  if (group.data && !slug) return <p className="text-slate-400">No problem assigned today.</p>;
  if (!problem.data) return <Loading />;

  return (
    <div className="space-y-4">
      <Link href={`/g/${groupId}`} className="text-sm text-slate-400 hover:text-slate-100">
        ← {group.data?.name}
      </Link>
      <div className="grid gap-6 lg:grid-cols-2">
        <Statement problem={problem.data} />
        <Workspace problem={problem.data} groupId={groupId} />
      </div>
    </div>
  );
}

function Statement({ problem: p }: { problem: Problem }) {
  return (
    <Card className="space-y-4 self-start">
      <div>
        <h1 className="text-2xl font-semibold">{p.title}</h1>
        <p className="mt-1 text-sm text-slate-400">
          {p.difficulty} · {p.topics.join(", ")} · {p.time_limit_ms} ms · {p.memory_limit_mb} MB
        </p>
      </div>
      <div className="markdown text-slate-300">
        <ReactMarkdown>{p.statement_md}</ReactMarkdown>
      </div>
      {p.samples.map((s, i) => (
        <div key={i} className="rounded-lg bg-slate-950 p-3 font-mono text-xs">
          <p className="mb-1 text-slate-500">Example {i + 1}</p>
          <p>
            <span className="text-slate-500">input </span>
            {JSON.stringify(s.input)}
          </p>
          <p>
            <span className="text-slate-500">output </span>
            {JSON.stringify(s.expected)}
          </p>
        </div>
      ))}
    </Card>
  );
}

type LiveTest = { i: number; verdict: string; ms: number | null };

function Workspace({ problem: p, groupId }: { problem: Problem; groupId: number }) {
  const queryClient = useQueryClient();
  const [language, setLanguage] = useState(p.languages[0]?.id ?? "python");
  const storageKey = `code:${p.slug}:${language}`;
  const [code, setCode] = useState("");
  const [activeId, setActiveId] = useState<number | null>(null);
  const [live, setLive] = useState<LiveTest[]>([]);

  // Code is kept per problem and language in this browser.
  useEffect(() => {
    let saved: string | null = null;
    try {
      saved = localStorage.getItem(storageKey);
    } catch {}
    setCode(saved ?? p.starter_code[language] ?? "");
  }, [storageKey, p.starter_code, language]);

  function onChange(value: string | undefined) {
    setCode(value ?? "");
    try {
      localStorage.setItem(storageKey, value ?? "");
    } catch {}
  }

  const submission = useQuery({
    queryKey: ["submission", activeId],
    queryFn: () =>
      unwrap(
        api.GET("/api/submissions/{submission_id}", {
          params: { path: { submission_id: activeId! } },
        }),
      ),
    enabled: activeId !== null,
    // Fallback if the WebSocket is down: poll until the verdict is in.
    refetchInterval: (q) => (q.state.data?.status === "done" ? false : 2000),
  });

  useTopic(activeId !== null ? `submission:${activeId}` : null, (msg) => {
    if (msg.event === "test") {
      const t = msg.data as unknown as LiveTest;
      setLive((prev) => [...prev.filter((x) => x.i !== t.i), t].sort((a, b) => a.i - b.i));
    }
    if (msg.event === "final") {
      queryClient.invalidateQueries({ queryKey: ["submission", activeId] });
      queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      queryClient.invalidateQueries({ queryKey: ["leaderboard", groupId] });
    }
  });

  const submit = useMutation({
    mutationFn: (kind: "run" | "submit") =>
      unwrap(
        api.POST("/api/submissions", {
          body: { problem_slug: p.slug, language, kind, code },
        }),
      ),
    onSuccess: (s) => {
      setLive([]);
      setActiveId(s.id);
    },
  });

  const s = submission.data;
  const busy = submit.isPending || (s !== undefined && s.status !== "done");

  return (
    <div className="space-y-4">
      <Card className="p-0">
        <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="rounded bg-slate-950 px-2 py-1 text-sm"
          >
            {p.languages.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
          <div className="flex gap-2">
            <Button variant="secondary" disabled={busy} onClick={() => submit.mutate("run")}>
              Run samples
            </Button>
            <Button disabled={busy} onClick={() => submit.mutate("submit")}>
              Submit
            </Button>
          </div>
        </div>
        <Editor
          height="420px"
          theme="vs-dark"
          language={p.languages.find((l) => l.id === language)?.monaco ?? language}
          value={code}
          onChange={onChange}
          options={{ minimap: { enabled: false }, fontSize: 14, scrollBeyondLastLine: false }}
        />
      </Card>
      <ErrorText error={submit.error} />
      {s && <Results submission={s} live={live} />}
    </div>
  );
}

function Results({ submission: s, live }: { submission: Schemas["SubmissionOut"]; live: LiveTest[] }) {
  const done = s.status === "done";
  const tests: LiveTest[] = done
    ? s.results.map((r) => ({ i: r.ordinal, verdict: r.verdict, ms: r.time_ms }))
    : live;
  return (
    <Card className="space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className={`text-lg font-semibold ${done ? verdictColor(s.verdict) : "text-slate-300"}`}>
          {done
            ? VERDICT_LABEL[s.verdict ?? ""] ?? s.verdict
            : s.status === "queued"
              ? "Queued…"
              : "Running…"}
        </h2>
        <span className="text-sm text-slate-400">
          {s.kind === "run" ? "samples" : "all tests"} · {done ? s.passed : tests.filter((t) => t.verdict === "AC").length}/
          {s.total || "?"} passed
          {done && s.runtime_ms != null && ` · ${s.runtime_ms} ms`}
        </span>
      </div>
      {done && s.verdict === "AC" && s.kind === "submit" && (
        <p className="text-sm text-emerald-400">Solved. Your group&apos;s streak thanks you.</p>
      )}
      <div className="flex flex-wrap gap-2">
        {tests.map((t) => (
          <span
            key={t.i}
            title={VERDICT_LABEL[t.verdict] ?? t.verdict}
            className={`rounded border border-slate-800 px-2 py-1 font-mono text-xs ${verdictColor(t.verdict)}`}
          >
            #{t.i + 1} {t.verdict}
            {t.ms != null && <span className="text-slate-500"> {t.ms}ms</span>}
          </span>
        ))}
      </div>
      {s.error && (
        <pre className="overflow-x-auto rounded bg-slate-950 p-3 text-xs text-rose-300">{s.error}</pre>
      )}
      {done &&
        s.results
          .filter((r) => r.sample && r.verdict !== "AC" && r.verdict !== "skipped")
          .slice(0, 1)
          .map((r) => (
            <div key={r.ordinal} className="space-y-1 rounded bg-slate-950 p-3 font-mono text-xs">
              <p className="text-slate-500">Failed example #{r.ordinal + 1}</p>
              <p>input {JSON.stringify(r.input)}</p>
              <p>expected {JSON.stringify(r.expected)}</p>
              <p>got {JSON.stringify(r.actual)}</p>
              {r.stdout && <pre className="whitespace-pre-wrap text-slate-400">stdout: {r.stdout}</pre>}
            </div>
          ))}
    </Card>
  );
}
