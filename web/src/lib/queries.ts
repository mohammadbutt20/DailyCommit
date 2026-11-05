"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { ApiError, api, unwrap } from "./api/client";

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => unwrap(api.GET("/api/me")),
    retry: false,
  });
}

/** useMe, but sends logged-out visitors to /login and back here afterwards. */
export function useRequireMe() {
  const me = useMe();
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => {
    if (me.error instanceof ApiError && me.error.status === 401) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [me.error, pathname, router]);
  return me;
}

export function useGroup(groupId: number) {
  return useQuery({
    queryKey: ["group", groupId],
    queryFn: () =>
      unwrap(api.GET("/api/groups/{group_id}", { params: { path: { group_id: groupId } } })),
  });
}
