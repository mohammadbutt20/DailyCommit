"use client";

import Editor from "@monaco-editor/react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Badge, Card, ErrorText, Eyebrow, Loading, cx } from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";
import { mono } from "@/lib/fonts";
import { VERDICT_LABEL, localDateTime, verdictColor, verdictSurface } from "@/lib/format";
import { useRequireMe } from "@/lib/queries";

const MONACO_LANGUAGE: Record<string, string> = { python: "python", java: "java", cpp: "cpp" };

/** One of your own submissions: the code you sent and how it did. The API only returns your
 *  own submissions (anyone else's is "not found"). */
export default function SubmissionPage() {
  const id = Number(useParams<{ id: string }>().id);
  const me = useRequireMe();
  const sub = useQuery({
    queryKey: ["submission", id],
    queryFn: () =>
      unwrap(api.GET("/api/submissions/{submission_id}", { params: { path: { submission_id: id } } })),
    enabled: me.isSuccess,
  });

  if (sub.isError) {
    return (
      <div className="space-y-3">
        <Link href="/me" className="text-xs text-faint hover:text-fg">
          ← My history
        </Link>
        <ErrorText error={sub.error} />
      </div>
    );
  }
  if (!sub.data) return <Loading />;
  const s = sub.data;

  return (
    <div className="space-y-5">
      <Link href="/me" className="text-xs text-faint transition-colors hover:text-fg">
        ← My history
      </Link>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Eyebrow>
            {s.kind === "practice" ? "Practice" : s.kind === "run" ? "Sample run" : "Submission"} #{s.id}
          </Eyebrow>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">{s.problem_title}</h1>
          <p className="mt-1 text-sm text-muted">
            {s.group ? (
              <Link href={`/g/${s.group.id}`} className="hover:text-fg">
                {s.group.name}
              </Link>
            ) : (
              "No group"
            )}{" "}
            · {s.language} · {localDateTime(s.created_at)}
          </p>
        </div>
        <div className={cx("rounded-xl border px-4 py-3 text-right", verdictSurface(s.verdict))}>
          <p className={cx("text-lg font-semibold", verdictColor(s.verdict))}>
            {s.status === "done" ? (VERDICT_LABEL[s.verdict ?? ""] ?? s.verdict) : "Running…"}
          </p>
          <p className="font-mono text-xs text-muted">
            {s.passed}/{s.total} passed{s.runtime_ms != null && ` · ${s.runtime_ms} ms`}
          </p>
        </div>
      </div>

      {s.error && (
        <pre className="overflow-x-auto rounded-lg border border-line bg-sunken p-3 font-mono text-xs text-danger">
          {s.error}
        </pre>
      )}

      <Card padded={false} className="overflow-hidden">
        <div className="border-b border-line px-4 py-2 text-xs text-faint">Your code (read-only)</div>
        <div className="h-[460px]">
          <Editor
            height="100%"
            theme="vs-dark"
            language={MONACO_LANGUAGE[s.language] ?? s.language}
            value={s.code}
            options={{
              readOnly: true,
              domReadOnly: true,
              minimap: { enabled: false },
              fontSize: 14,
              lineHeight: 22,
              fontFamily: mono.style.fontFamily,
              scrollBeyondLastLine: false,
              automaticLayout: true,
            }}
          />
        </div>
      </Card>

      {s.results.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {s.results.map((r) => (
            <Badge key={r.ordinal}>
              <span className={verdictColor(r.verdict)}>
                #{r.ordinal + 1} {r.verdict}
              </span>
              {r.time_ms != null && <span className="ml-1 text-faint">{r.time_ms}ms</span>}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
