import { Suspense } from "react";
import Link from "next/link";
import { House, Store, ScanLine, User } from "lucide-react";
import { ActiveMarker } from "./active-marker";

const TABS = [
  { href: "/", label: "Home", Icon: House, match: ["/"] },
  { href: "/stores", label: "Stores", Icon: Store, match: ["/stores", "/store"] },
  { href: "/pay", label: "Pay", Icon: ScanLine, match: ["/pay"] },
  { href: "/profile", label: "Profile", Icon: User, match: ["/profile"] },
];

/** The toolbar at the bottom of every customer screen. */
export function BottomNav() {
  return (
    <nav className="fixed bottom-0 inset-x-0 border-t border-stone-200 bg-white/95 backdrop-blur pb-[env(safe-area-inset-bottom)]">
      <div className="max-w-md mx-auto grid grid-cols-4">
        {TABS.map(({ href, label, Icon, match }) => (
          <Link
            key={href}
            href={href}
            className="flex flex-col items-center gap-1 py-3 text-xs text-stone-400 hover:text-stone-900 has-[[data-active]]:text-green-700"
          >
            <Icon size={22} strokeWidth={1.75} />
            {label}
            <Suspense>
              <ActiveMarker match={match} />
            </Suspense>
          </Link>
        ))}
      </div>
    </nav>
  );
}
