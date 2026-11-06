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

const LOGIN_ERRORS: Record<string, string> = {
  discord_denied: "Discord sign-in was cancelled.",
  discord_state: "That sign-in link expired or was already used. Please try again.",
  discord_failed: "Couldn't reach Discord to finish signing in. Please try again.",
};

function DiscordMark() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden>
      <path d="M20.32 4.37a19.8 19.8 0 0 0-4.89-1.52.07.07 0 0 0-.08.04c-.21.38-.44.87-.61 1.25a18.27 18.27 0 0 0-5.48 0 12.6 12.6 0 0 0-.62-1.25.08.08 0 0 0-.08-.04 19.74 19.74 0 0 0-4.89 1.52.07.07 0 0 0-.03.03C.53 9.05-.32 13.58.1 18.06a.08.08 0 0 0 .03.06 19.9 19.9 0 0 0 5.99 3.03.08.08 0 0 0 .08-.03c.46-.63.87-1.3 1.23-2a.08.08 0 0 0-.04-.1 13.1 13.1 0 0 1-1.87-.9.08.08 0 0 1 0-.12l.37-.29a.07.07 0 0 1 .08-.01c3.93 1.79 8.18 1.79 12.07 0a.07.07 0 0 1 .08.01l.37.29a.08.08 0 0 1 0 .12c-.6.35-1.22.65-1.87.9a.08.08 0 0 0-.04.1c.36.7.78 1.37 1.23 2a.08.08 0 0 0 .08.03 19.84 19.84 0 0 0 6-3.03.08.08 0 0 0 .03-.05c.5-5.18-.84-9.67-3.55-13.66a.06.06 0 0 0-.03-.03ZM8.02 15.33c-1.18 0-2.16-1.08-2.16-2.42 0-1.33.96-2.42 2.16-2.42 1.21 0 2.18 1.1 2.16 2.42 0 1.34-.96 2.42-2.16 2.42Zm7.97 0c-1.18 0-2.15-1.08-2.15-2.42 0-1.33.95-2.42 2.15-2.42 1.21 0 2.18 1.1 2.16 2.42 0 1.34-.95 2.42-2.16 2.42Z" />
    </svg>
  );
}

function LoginCard() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/groups";
  const loginError = LOGIN_ERRORS[params.get("error") ?? ""];
  const queryClient = useQueryClient();
  const [name, setName] = useState("");

  const providers = useQuery({
    queryKey: ["auth-providers"],
    queryFn: () => unwrap(api.GET("/api/auth/providers")),
    staleTime: Infinity,
  });
  const devEnabled = providers.data?.dev ?? false;
  const discordEnabled = providers.data?.discord ?? false;
  const users = useQuery({
    queryKey: ["dev-users"],
    queryFn: () => unwrap(api.GET("/api/auth/dev/users")),
    enabled: devEnabled,
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
          {discordEnabled
            ? "Use your Discord account. We only see your name and avatar."
            : devEnabled
              ? "Dev login: pick any name. Set DISCORD_CLIENT_ID/SECRET to enable Discord."
              : providers.isPending
                ? "Loading sign-in options…"
                : "No sign-in method is configured."}
        </p>
        {loginError && (
          <p className="mt-4 rounded-lg border border-[#f8514933] bg-[#f851491a] px-3 py-2 text-sm text-[#ff7b72]">
            {loginError}
          </p>
        )}
        {discordEnabled && (
          // A real navigation, not fetch: the browser has to follow the redirects to Discord and back.
          <a
            href={`/api/auth/discord/login?next=${encodeURIComponent(next)}`}
            className="mt-6 flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-[#5865F2] text-sm font-semibold text-white transition-colors hover:bg-[#4752C4]"
          >
            <DiscordMark />
            Continue with Discord
          </a>
        )}
        {devEnabled && discordEnabled && (
          <div className="mt-6 flex items-center gap-3">
            <span className="h-px flex-1 bg-line" />
            <Eyebrow>dev login</Eyebrow>
            <span className="h-px flex-1 bg-line" />
          </div>
        )}
        {devEnabled && (
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
        )}
        {devEnabled && users.data && users.data.length > 0 && (
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
      <LoginCard />
    </Suspense>
  );
}
