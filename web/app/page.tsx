"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ShoppingBag, HandCoins } from "lucide-react";
import { getMe, getName, getUserId, logout, errorMessage, ApiError, type Me } from "@/lib/api";
import { formatMoney, formatDate } from "@/lib/format";
import { storeName, storeLocation } from "@/lib/stores";
import { CURRENT_PROGRAM } from "@/lib/programs";
import { Screen, Card, Spinner, ErrorText, VerifyLink } from "@/components/ui";
import { ProgramSwitcher } from "@/components/program-switcher";

export default function HomePage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getUserId()) {
      router.replace("/login");
      return;
    }
    getMe()
      .then((m) => {
        setMe(m);
        setName(getName() || m.email);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.code === "USER_NOT_FOUND") {
          logout();
          router.replace("/login");
        } else {
          setError(errorMessage(err));
        }
      });
  }, [router]);

  if (error) return <Screen nav><ErrorText>{error}</ErrorText></Screen>;
  if (!me) return <Screen nav><div className="pt-20 text-center text-stone-400"><Spinner /></div></Screen>;

  const unlocked = me.points >= me.min_points_to_spend;
  const progress = Math.min(100, (me.points / me.min_points_to_spend) * 100);

  return (
    <Screen nav>
      <header>
        <p className="font-semibold">$APP Rewards</p>
        <p className="text-stone-500">Welcome back, {name}</p>
      </header>

      <ProgramSwitcher />

      {/* Points */}
      <Card className="text-center py-8">
        <p className="text-sm text-stone-500">Your {CURRENT_PROGRAM.name} points</p>
        <p className="text-6xl font-semibold tracking-tight my-2">{me.points}</p>
        {unlocked ? (
          <p className="text-green-700 font-medium">
            {formatMoney(me.points_value_cents, "USD")} ready to spend
          </p>
        ) : (
          <div className="space-y-2 pt-2">
            <div className="h-2 rounded-full bg-stone-100 overflow-hidden">
              <div className="h-full bg-green-700 rounded-full" style={{ width: `${progress}%` }} />
            </div>
            <p className="text-sm text-stone-500">
              {me.min_points_to_spend - me.points} more points until you can spend them
            </p>
          </div>
        )}
      </Card>

      {/* Actions */}
      <div className="grid grid-cols-2 gap-3">
        <Link href="/stores">
          <Card className="hover:border-stone-400 transition h-full">
            <IconCircle><ShoppingBag size={20} strokeWidth={1.75} /></IconCircle>
            <p className="font-medium">Shop</p>
            <p className="text-sm text-stone-500">Earn points</p>
          </Card>
        </Link>
        <Link href="/pay">
          <Card className="hover:border-stone-400 transition h-full">
            <IconCircle><HandCoins size={20} strokeWidth={1.75} /></IconCircle>
            <p className="font-medium">Pay in store</p>
            <p className="text-sm text-stone-500">Use your points</p>
          </Card>
        </Link>
      </div>

      {/* History */}
      <section className="space-y-3">
        <h2 className="text-sm font-medium text-stone-500">Activity</h2>
        {me.history.length === 0 ? (
          <p className="text-sm text-stone-400">No activity yet. Shop at {storeName("brand-a-us")} to earn your first points.</p>
        ) : (
          <Card className="p-0 divide-y divide-stone-100">
            {me.history.map((item) => (
              <div key={item.tx_hash} className="flex items-center justify-between px-5 py-4">
                <div>
                  <p className="font-medium">{storeName(item.brand)}</p>
                  <p className="text-xs text-stone-400">
                    {storeLocation(item.brand)} · {formatDate(item.at)}
                  </p>
                  <VerifyLink url={item.explorer_url} />
                </div>
                <p className={item.type === "earned" ? "text-green-700 font-medium" : "font-medium"}>
                  {item.type === "earned" ? "+" : "−"}
                  {item.points}
                </p>
              </div>
            ))}
          </Card>
        )}
      </section>

      <footer className="pt-8 text-center text-xs text-stone-400 space-x-3">
        <span>Demo screens:</span>
        <Link href="/cashier" className="underline hover:text-stone-900">Café cashier</Link>
        <Link href="/payouts" className="underline hover:text-stone-900">Brand payouts</Link>
      </footer>
    </Screen>
  );
}

function IconCircle({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-green-50 text-green-700">
      {children}
    </div>
  );
}
