"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Statement, Workspace } from "@/components/ProblemWorkspace";
import { Badge, ErrorText, Eyebrow, Loading } from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";
import { dayLabel } from "@/lib/format";
import { useGroup, useRequireMe } from "@/lib/queries";

/** A past daily problem in the normal editor. Submissions here are kind "practice": judged on
 *  every test, never counted toward any streak or day. */
export default function PracticePage() {
  const params = useParams<{ groupId: string; day: string }>();
  const groupId = Number(params.groupId);
  const me = useRequireMe();
  const group = useGroup(groupId);
  const entry = useQuery({
    queryKey: ["history", groupId, params.day],
    queryFn: () =>
      unwrap(
        api.GET("/api/groups/{group_id}/history/{day}", {
          params: { path: { group_id: groupId, day: params.day } },
        }),
      ),
    enabled: me.isSuccess,
  });
  const slug = entry.data?.problem.slug;
  const problem = useQuery({
    queryKey: ["problem", slug],
    queryFn: () => unwrap(api.GET("/api/problems/{slug}", { params: { path: { slug: slug! } } })),
    enabled: !!slug,
  });

  if (entry.isError) return <ErrorText error={entry.error} />;
  if (!problem.data || !entry.data) return <Loading />;

  return (
    <div className="flex flex-col gap-3 lg:h-[calc(100vh-120px)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          href={`/g/${groupId}/history`}
          className="text-xs text-faint transition-colors hover:text-fg"
        >
          ← Past problems · {group.data?.name}
        </Link>
        <div className="flex items-center gap-2">
          <Badge tone="warn">practice · doesn&apos;t count toward any streak</Badge>
          <Eyebrow>{dayLabel(entry.data.day)}</Eyebrow>
        </div>
      </div>
      {problem.data.judgeable ? (
        <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <Statement problem={problem.data} />
          <Workspace problem={problem.data} groupId={groupId} mode="practice" />
        </div>
      ) : (
        <p className="text-muted">
          This problem can&apos;t be judged here.{" "}
          {problem.data.source_url && (
            <a href={problem.data.source_url} className="text-accent" target="_blank" rel="noopener noreferrer">
              Practice it on LeetCode
            </a>
          )}
        </p>
      )}
    </div>
  );
}
