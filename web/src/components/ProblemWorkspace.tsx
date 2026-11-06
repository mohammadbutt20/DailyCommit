"use client";

// The problem statement and the Monaco workspace (editor, Run / Submit, live per-test results),
// shared by today's problem and the practice page for past problems.

import Editor, { type BeforeMount, type OnMount } from "@monaco-editor/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Badge, Button, Difficulty, ErrorText, Loading, Select, Spinner, cx } from "@/components/ui";
import { api, type Schemas, unwrap } from "@/lib/api/client";
import { mono } from "@/lib/fonts";
import { VERDICT_LABEL, verdictColor, verdictSurface } from "@/lib/format";
import { useTopic } from "@/lib/ws";

type Problem = Schemas["ProblemDetail"];

export function Statement({ problem: p }: { problem: Problem }) {
  return (
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
          <span className="ml-auto font-mono text-[11px] text-faint">
            {p.time_limit_ms} ms · {p.memory_limit_mb} MB
          </span>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        {p.statement_html != null ? (
          // LeetCode's statement, sanitized on import (backend leetcode/importer.py).
          <div
            className="markdown leetcode-statement text-[15px]"
            dangerouslySetInnerHTML={{ __html: p.statement_html }}
          />
        ) : (
          <div className="markdown text-[15px]">
            <ReactMarkdown>{p.statement_md}</ReactMarkdown>
          </div>
        )}
        <div className="mt-6 space-y-3">
          {p.samples.map((s, i) => (
            <div key={i} className="overflow-hidden rounded-lg border border-line bg-sunken">
              <p className="border-b border-line px-3 py-1.5 text-xs font-medium text-muted">
                Sample test {i + 1}
              </p>
              <div className="space-y-1.5 px-3 py-2.5 font-mono text-[13px]">
                <IO label="input" value={s.input} />
                <IO label="output" value={s.expected} />
              </div>
            </div>
          ))}
        </div>
        {p.source_url && (
          <p className="mt-6 text-xs text-faint">
            Problem from{" "}
            <a href={p.source_url} target="_blank" rel="noopener noreferrer" className="hover:text-fg">
              LeetCode
            </a>
            . Judged here with our own tests.
          </p>
        )}
      </div>
    </section>
  );
}

function IO({ label, value, tone }: { label: string; value: unknown; tone?: string }) {
  return (
    <p className="flex gap-3">
      <span className="w-14 shrink-0 text-faint">{label}</span>
      <span className={cx("break-all", tone ?? "text-fg")}>{JSON.stringify(value)}</span>
    </p>
  );
}

const defineTheme: BeforeMount = (monaco) => {
  monaco.editor.defineTheme("daily-commit", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "5d6675", fontStyle: "italic" },
      { token: "keyword", foreground: "c792ea" },
      { token: "string", foreground: "a5e3b5" },
      { token: "number", foreground: "f2b84b" },
      { token: "type", foreground: "7dcfff" },
    ],
    colors: {
      "editor.background": "#0c0f12",
      "editor.foreground": "#e7eaef",
      "editorLineNumber.foreground": "#3a424f",
      "editorLineNumber.activeForeground": "#8f98a6",
      "editor.lineHighlightBackground": "#12161b",
      "editor.lineHighlightBorder": "#00000000",
      "editor.selectionBackground": "#3fd68f33",
      "editor.inactiveSelectionBackground": "#3fd68f1a",
      "editorCursor.foreground": "#3fd68f",
      "editorIndentGuide.background1": "#1a1f26",
      "editorIndentGuide.activeBackground1": "#2c333d",
      "editorWidget.background": "#101317",
      "editorWidget.border": "#2c333d",
      "scrollbarSlider.background": "#ffffff12",
      "scrollbarSlider.hoverBackground": "#ffffff20",
    },
  });
};

// Monaco measures glyphs once; re-measure after the web font arrives so the cursor lines up.
const remeasure: OnMount = (_editor, monaco) => {
  document.fonts?.ready.then(() => monaco.editor.remeasureFonts());
};

type LiveTest = { i: number; verdict: string; ms: number | null };

/** "daily": today's problem, Submit can keep the streak alive. "practice": a past problem,
 *  Submit runs every test but is never counted toward any streak or day (kind "practice"). */
export type WorkspaceMode = "daily" | "practice";

export function Workspace({
  problem: p,
  groupId,
  mode = "daily",
}: {
  problem: Problem;
  groupId: number;
  mode?: WorkspaceMode;
}) {
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

  function resetCode() {
    const starter = p.starter_code[language] ?? "";
    setCode(starter);
    try {
      localStorage.removeItem(storageKey);
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
    // Fallback if the WebSocket is down: poll until the verdict is in. IE is provisional (a
    // retried job can still replace it with the real result), so keep checking, slowly.
    refetchInterval: (q) => {
      const d = q.state.data;
      if (d?.status !== "done") return 2000;
      return d.verdict === "IE" ? 10_000 : false;
    },
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
    mutationFn: (kind: "run" | "submit" | "practice") =>
      unwrap(
        api.POST("/api/submissions", {
          body: { problem_slug: p.slug, language, kind, code, group_id: groupId },
        }),
      ),
    onSuccess: (s) => {
      setLive([]);
      setActiveId(s.id);
    },
  });

  const s = submission.data;
  const busy = submit.isPending || (s !== undefined && s.status !== "done");
  const pendingKind = submit.isPending ? submit.variables : s && s.status !== "done" ? s.kind : null;

  return (
    <div className="flex min-h-0 flex-col gap-3">
      <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-line bg-sunken">
        <div className="flex items-center justify-between gap-3 border-b border-line bg-surface px-3 py-2">
          <div className="flex items-center gap-2">
            <Select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="h-8 w-auto text-xs"
            >
              {p.languages.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </Select>
            <Button variant="ghost" size="sm" onClick={resetCode} title="Restore the starter code">
              Reset
            </Button>
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={busy}
              onClick={() => submit.mutate("run")}
            >
              {pendingKind === "run" ? <Spinner /> : "▶"} Run samples
            </Button>
            <Button
              size="sm"
              disabled={busy}
              onClick={() => submit.mutate(mode === "practice" ? "practice" : "submit")}
            >
              {(pendingKind === "submit" || pendingKind === "practice") && <Spinner />}
              {mode === "practice" ? "Submit (practice)" : "Submit"}
            </Button>
          </div>
        </div>
        <div className="h-[440px] lg:h-auto lg:min-h-0 lg:flex-1">
          <Editor
            height="100%"
            theme="daily-commit"
            beforeMount={defineTheme}
            onMount={remeasure}
            loading={<Loading />}
            language={p.languages.find((l) => l.id === language)?.monaco ?? language}
            value={code}
            onChange={onChange}
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              lineHeight: 22,
              fontFamily: mono.style.fontFamily,
              fontLigatures: true,
              scrollBeyondLastLine: false,
              padding: { top: 14, bottom: 14 },
              renderLineHighlight: "all",
              smoothScrolling: true,
              cursorBlinking: "smooth",
              automaticLayout: true,
            }}
          />
        </div>
      </section>
      <ErrorText error={submit.error} />
      <div className="lg:max-h-[42%] lg:shrink-0 lg:overflow-y-auto">
        {s ? (
          <Results submission={s} live={live} />
        ) : (
          <div className="rounded-xl border border-dashed border-line px-4 py-3 text-xs text-faint">
            <span className="text-muted">Run samples</span> checks the examples.{" "}
            {mode === "practice" ? (
              <>
                <span className="text-muted">Submit (practice)</span> runs every test. Practice
                never counts toward any streak or day.
              </>
            ) : (
              <>
                <span className="text-muted">Submit</span> runs every test and counts toward the
                streak.
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Results({ submission: s, live }: { submission: Schemas["SubmissionOut"]; live: LiveTest[] }) {
  const done = s.status === "done";
  const tests: LiveTest[] = done
    ? s.results.map((r) => ({ i: r.ordinal, verdict: r.verdict, ms: r.time_ms }))
    : live;
  const passed = done ? s.passed : tests.filter((t) => t.verdict === "AC").length;
  const failedSample = done
    ? s.results.find((r) => r.sample && r.verdict !== "AC" && r.verdict !== "skipped")
    : undefined;

  return (
    <section
      className={cx(
        "rounded-xl border p-4",
        done ? verdictSurface(s.verdict) : "border-line bg-surface",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          {!done && <Spinner className="text-muted" />}
          <h2
            className={cx(
              "text-lg font-semibold tracking-tight",
              done ? verdictColor(s.verdict) : "text-fg",
            )}
          >
            {done
              ? (VERDICT_LABEL[s.verdict ?? ""] ?? s.verdict)
              : s.status === "queued"
                ? "Queued…"
                : "Running…"}
          </h2>
          <Badge>
            {s.kind === "run" ? "samples" : s.kind === "practice" ? "practice · not counted" : "all tests"}
          </Badge>
        </div>
        <span className="font-mono text-xs text-muted">
          <span className="text-fg">{passed}</span>/{s.total || "?"} passed
          {done && s.runtime_ms != null && ` · ${s.runtime_ms} ms`}
        </span>
      </div>

      {done && s.verdict === "AC" && s.kind === "submit" && (
        <p className="mt-2 text-sm text-accent">Solved. Your group&apos;s streak thanks you.</p>
      )}

      {done && s.verdict === "AC" && s.kind === "practice" && (
        <p className="mt-2 text-sm text-accent">
          Accepted. Practice only: no streak or day was changed.
        </p>
      )}

      {tests.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {tests.map((t) => (
            <span
              key={t.i}
              title={VERDICT_LABEL[t.verdict] ?? t.verdict}
              className={cx(
                "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[11px]",
                verdictSurface(t.verdict),
                verdictColor(t.verdict),
              )}
            >
              <span className="text-faint">#{t.i + 1}</span>
              {t.verdict}
              {t.ms != null && <span className="text-faint">{t.ms}ms</span>}
            </span>
          ))}
        </div>
      )}

      {s.error && (
        <pre className="mt-3 overflow-x-auto rounded-lg border border-line bg-sunken p-3 font-mono text-xs text-danger">
          {s.error}
        </pre>
      )}

      {failedSample && (
        <div className="mt-3 overflow-hidden rounded-lg border border-line bg-sunken">
          <p className="border-b border-line px-3 py-1.5 text-xs font-medium text-muted">
            Failed example #{failedSample.ordinal + 1}
          </p>
          <div className="space-y-1.5 px-3 py-2.5 font-mono text-[13px]">
            <IO label="input" value={failedSample.input} />
            <IO label="expected" value={failedSample.expected} tone="text-accent" />
            <IO label="got" value={failedSample.actual} tone="text-danger" />
            {failedSample.stdout && (
              <pre className="mt-2 border-t border-line pt-2 whitespace-pre-wrap text-muted">
                <span className="text-faint">stdout </span>
                {failedSample.stdout}
              </pre>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
