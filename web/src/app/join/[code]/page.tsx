"use client";

import { useMutation } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import { ErrorText, Loading } from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";
import { useRequireMe } from "@/lib/queries";

export default function JoinPage() {
  const { code } = useParams<{ code: string }>();
  const me = useRequireMe();
  const router = useRouter();
  const join = useMutation({
    mutationFn: () => unwrap(api.POST("/api/groups/join", { body: { invite_code: code } })),
    onSuccess: (g) => router.replace(`/g/${g.id}`),
  });
  const { mutate } = join;

  useEffect(() => {
    // Joining is idempotent, so a double run in dev strict mode is harmless.
    if (me.isSuccess) mutate();
  }, [me.isSuccess, mutate]);

  return join.isError ? <ErrorText error={join.error} /> : <Loading />;
}
