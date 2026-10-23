"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Button, Card, ErrorText, Input } from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";

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
    <div className="mx-auto mt-16 max-w-md">
      <h1 className="mb-2 text-2xl font-semibold">Log in</h1>
      <p className="mb-6 text-sm text-slate-400">
        Dev login: choose any name. Real sign-in with Discord comes later.
      </p>
      <Card className="space-y-4">
        <form
          className="flex gap-2"
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
            Continue
          </Button>
        </form>
        {users.data && users.data.length > 0 && (
          <div>
            <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Or continue as</p>
            <div className="flex flex-wrap gap-2">
              {users.data.map((u) => (
                <Button
                  key={u.id}
                  variant="secondary"
                  onClick={() => login.mutate(u.display_name)}
                  disabled={login.isPending}
                >
                  {u.display_name}
                </Button>
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
