"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import { useMe } from "@/lib/queries";

export default function Header() {
  const me = useMe();
  const router = useRouter();
  const queryClient = useQueryClient();

  async function logout() {
    await api.POST("/api/auth/logout");
    queryClient.clear();
    router.push("/login");
  }

  return (
    <header className="border-b border-slate-800">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <Link href="/groups" className="font-mono text-lg font-semibold text-emerald-400">
          daily_commit
        </Link>
        {me.data && (
          <div className="flex items-center gap-4 text-sm">
            <span className="text-slate-300">{me.data.user.display_name}</span>
            <button onClick={logout} className="text-slate-400 hover:text-slate-100">
              Log out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
