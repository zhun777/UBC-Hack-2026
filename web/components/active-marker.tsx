"use client";

import { usePathname } from "next/navigation";

/** Marks its parent tab as active (styled with has-[[data-active]]:) when the URL matches. */
export function ActiveMarker({ match }: { match: string[] }) {
  const pathname = usePathname();
  const active = match.some((m) => (m === "/" ? pathname === "/" : pathname === m || pathname.startsWith(`${m}/`)));
  return active ? <span data-active hidden /> : null;
}
