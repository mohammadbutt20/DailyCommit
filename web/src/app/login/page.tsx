"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Avatar, Button, Card, ErrorText, Eyebrow, Input, Spinner } from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";

// Decorative contribution grid: deterministic so server and client render the same thing.
function HeroGraph() {
  const cols = 18;
  const rows = 5;
  const cells = Array.from({ length: cols * rows }, (_, i) => {
    const col = i % cols;
    const v = (Math.imul(i + 1, 2654435761) >>> 0) / 2 ** 32;
    const level = v * (0.35 + col / cols);
    return level > 0.62 ? 3 : level > 0.42 ? 2 : level > 0.25 ? 1 : 0;
  });
  const shade = ["bg-cell-empty", "bg-[#1d4a35]", "bg-[#2a8a5c]", "bg-accent"];
  return (
    <div
      className="grid gap-[5px]"
      style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
      aria-hidden
    >
      {cells.map((l, i) => (
        <span key={i} className={`aspect-square rounded-[4px] ${shade[l]}`} />
      ))}
    </div>
  );
}

// Dev login only for now: pick a name, no password. Discord OAuth is a later slice.
function DevLogin() {
  const router = useRouter();
  const next = useSearchParams().get("next") || "/groups";
  const queryClient = useQueryClient();
  const [name, setName] = useState("");

  const users = useQuery({
    queryKey: ["dev-users"],
    queryFn: () => unwrap(api.GET("/api/auth/dev/users")),
  });
  const login = useMutation({
    mutationFn: (n: string) => unwrap(api.POST("/api/auth/dev/login", { body: { name: n } })),
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      router.replace(next.startsWith("/") ? next : "/groups");
    },
  });

  return (
    <div className="mx-auto grid max-w-5xl items-center gap-12 pt-8 lg:grid-cols-[1.1fr_1fr] lg:pt-16">
      <div>
        <Eyebrow className="text-accent">git commit -m &quot;day 1&quot;</Eyebrow>
        <h1 className="mt-4 text-4xl leading-[1.1] font-semibold tracking-tight text-balance sm:text-5xl">
          One problem a day.
          <br />
          <span className="text-muted">One streak, together.</span>
        </h1>
        <p className="mt-5 max-w-md text-[15px] leading-relaxed text-muted">
          Your group gets the same problem every day. Solve it in the browser, keep the group
          streak alive, and see who got there first.
        </p>
        <div className="mt-10 max-w-md rounded-xl border border-line bg-surface/60 p-4">
          <HeroGraph />
        </div>
      </div>

      <Card className="p-6 sm:p-7">
        <h2 className="text-lg font-semibold tracking-tight">Sign in</h2>
        <p className="mt-1 text-sm text-muted">
          Dev login: pick any name. Discord sign-in comes later.
        </p>
        <form
          className="mt-6 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) login.mutate(name.trim());
          }}
        >
          <Input
            placeholder="Your name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={32}
            autoFocus
          />
          <Button type="submit" disabled={login.isPending || !name.trim()}>
            {login.isPending ? <Spinner /> : "Continue"}
          </Button>
        </form>
        {users.data && users.data.length > 0 && (
          <div className="mt-7">
            <div className="mb-3 flex items-center gap-3">
              <span className="h-px flex-1 bg-line" />
              <Eyebrow>or continue as</Eyebrow>
              <span className="h-px flex-1 bg-line" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              {users.data.map((u) => (
                <button
                  key={u.id}
                  onClick={() => login.mutate(u.display_name)}
                  disabled={login.isPending}
                  className="flex items-center gap-2.5 rounded-lg border border-line bg-raised px-3 py-2 text-left text-sm transition-colors hover:border-line-strong hover:bg-[#1c2128] disabled:opacity-50"
                >
                  <Avatar name={u.display_name} size="sm" />
                  <span className="truncate">{u.display_name}</span>
                </button>
              ))}
            </div>
          </div>
        )}
        <ErrorText error={login.error} />
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <DevLogin />
    </Suspense>
  );
}
