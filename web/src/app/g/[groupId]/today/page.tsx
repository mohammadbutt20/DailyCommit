"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { LeetCodeProblem } from "@/components/LeetCodeProblem";
import { Statement, Workspace } from "@/components/ProblemWorkspace";
import { ErrorText, Eyebrow, Loading } from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";
import { useGroup, useRequireMe } from "@/lib/queries";

export default function TodayPage() {
  const groupId = Number(useParams<{ groupId: string }>().groupId);
  const me = useRequireMe();
  const group = useGroup(groupId);
  const slug = group.data?.today_problem?.slug;
  const problem = useQuery({
    queryKey: ["problem", slug],
    queryFn: () => unwrap(api.GET("/api/problems/{slug}", { params: { path: { slug: slug! } } })),
    enabled: !!slug,
  });

  if (group.isError) return <ErrorText error={group.error} />;
  if (group.data && !slug) return <p className="text-muted">No problem assigned today.</p>;
  if (!problem.data) return <Loading />;

  return (
    // On large screens the page is a fixed-height IDE: header 56px + main padding 64px.
    <div className="flex flex-col gap-3 lg:h-[calc(100vh-120px)]">
      <div className="flex items-center justify-between gap-4">
        <Link href={`/g/${groupId}`} className="text-xs text-faint transition-colors hover:text-fg">
          ← {group.data?.name}
        </Link>
        <Eyebrow>Today · {group.data?.today}</Eyebrow>
      </div>
      {/* LeetCode problems without a judge pack are solved on leetcode.com; everything
          judgeable (local, or LeetCode with a pack) is solved here in the editor. */}
      {!problem.data.judgeable && group.data ? (
        <LeetCodeProblem problem={problem.data} group={group.data} userId={me.data?.user.id} />
      ) : (
        <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <Statement problem={problem.data} />
          <Workspace problem={problem.data} groupId={groupId} />
        </div>
      )}
    </div>
  );
}
