"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Loading } from "@/components/ui";
import { useMe } from "@/lib/queries";

export default function Home() {
  const me = useMe();
  const router = useRouter();
  useEffect(() => {
    if (me.isSuccess) router.replace("/groups");
    if (me.isError) router.replace("/login");
  }, [me.isSuccess, me.isError, router]);
  return <Loading />;
}
