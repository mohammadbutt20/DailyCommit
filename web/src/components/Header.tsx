"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import { useMe } from "@/lib/queries";
import { Avatar } from "./ui";

export function Logo() {
  return (
    <span className="flex items-center gap-2.5">
      <svg viewBox="0 0 24 24" className="h-6 w-6" aria-hidden>
        <rect width="24" height="24" rx="6" fill="#3fd68f" />
        <path d="M12 4v5.2M12 14.8V20" stroke="#03140c" strokeWidth="2.2" strokeLinecap="round" />
        <circle cx="12" cy="12" r="3.2" fill="none" stroke="#03140c" strokeWidth="2.2" />
      </svg>
      <span className="font-mono text-[15px] font-semibold tracking-tight text-fg">
        daily<span className="text-accent">_</span>commit
      </span>
    </span>
  );
}

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
    <header className="sticky top-0 z-20 border-b border-line bg-canvas/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between px-4 sm:px-6">
        <Link href="/groups" className="rounded-md">
          <Logo />
        </Link>
        {me.data && (
          <div className="flex items-center gap-1">
            <Link
              href="/groups"
              className="hidden rounded-md px-3 py-1.5 text-sm text-muted transition-colors hover:bg-raised hover:text-fg sm:block"
            >
              Groups
            </Link>
            <div className="mx-2 hidden h-5 w-px bg-line sm:block" />
            <div className="flex items-center gap-2 pr-1">
              <Avatar name={me.data.user.display_name} src={me.data.user.avatar_url} size="sm" />
              <span className="text-sm text-fg">{me.data.user.display_name}</span>
            </div>
            <button
              onClick={logout}
              className="rounded-md px-3 py-1.5 text-sm text-muted transition-colors hover:bg-raised hover:text-fg"
            >
              Log out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
