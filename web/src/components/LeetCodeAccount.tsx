"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, ErrorText, Input, Spinner } from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";

export const LEETCODE_ACCOUNT_KEY = ["leetcode-account"];

export function useLeetCodeAccount() {
  return useQuery({
    queryKey: LEETCODE_ACCOUNT_KEY,
    queryFn: () => unwrap(api.GET("/api/me/leetcode")),
  });
}

/** Link (with an ownership check), show, or unlink the user's LeetCode account. */
export function LeetCodeAccount({ compact = false }: { compact?: boolean }) {
  const queryClient = useQueryClient();
  const account = useLeetCodeAccount();
  const [username, setUsername] = useState("");
  const [copied, setCopied] = useState(false);
  const refresh = (data: unknown) => queryClient.setQueryData(LEETCODE_ACCOUNT_KEY, data);

  const link = useMutation({
    mutationFn: () => unwrap(api.PUT("/api/me/leetcode", { body: { username: username.trim() } })),
    onSuccess: refresh,
  });
  const verify = useMutation({
    mutationFn: () => unwrap(api.POST("/api/me/leetcode/verify")),
    onSuccess: refresh,
  });
  const unlink = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/me/leetcode")),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: LEETCODE_ACCOUNT_KEY }),
  });

  if (!account.data) return account.isError ? <ErrorText error={account.error} /> : <Spinner />;
  const a = account.data;

  if (a.username) {
    return (
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="text-muted">
          LeetCode:{" "}
          <a
            href={`https://leetcode.com/u/${a.username}/`}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-fg hover:text-accent"
          >
            {a.username}
          </a>
        </span>
        {!compact && (
          <Button variant="ghost" size="sm" onClick={() => unlink.mutate()} disabled={unlink.isPending}>
            Unlink
          </Button>
        )}
      </div>
    );
  }

  if (a.pending_username && a.verify_code) {
    const code = a.verify_code;
    return (
      <div className="space-y-3 text-sm">
        <p className="text-muted">
          To prove <span className="font-medium text-fg">{a.pending_username}</span> is yours,
          paste this code anywhere in the <span className="text-fg">Summary</span> on your{" "}
          <a
            href="https://leetcode.com/profile/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:underline"
          >
            LeetCode profile
          </a>
          , save, then verify. You can remove it afterwards.
        </p>
        <div className="flex items-center gap-2">
          <code className="flex-1 rounded-lg border border-line bg-sunken px-3 py-2 font-mono text-[13px]">
            {code}
          </code>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              navigator.clipboard?.writeText(code).then(() => setCopied(true));
            }}
          >
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => verify.mutate()} disabled={verify.isPending}>
            {verify.isPending ? <Spinner /> : "Verify"}
          </Button>
          <Button variant="ghost" onClick={() => unlink.mutate()} disabled={unlink.isPending}>
            Use a different account
          </Button>
        </div>
        <ErrorText error={verify.error} />
      </div>
    );
  }

  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (username.trim()) link.mutate();
      }}
    >
      {!compact && (
        <p className="text-sm text-muted">
          Link your LeetCode account so solves on leetcode.com count for your group.
        </p>
      )}
      <div className="flex gap-2">
        <Input
          placeholder="LeetCode username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          maxLength={64}
        />
        <Button type="submit" disabled={!username.trim() || link.isPending}>
          {link.isPending ? <Spinner /> : "Link"}
        </Button>
      </div>
      <ErrorText error={link.error} />
    </form>
  );
}
