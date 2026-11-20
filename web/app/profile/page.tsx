"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { getMe, getName, getUserId, logout, errorMessage, type Me } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { Screen, Card, Button, Spinner, ErrorText } from "@/components/ui";

export default function ProfilePage() {
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
      .catch((err) => setError(errorMessage(err)));
  }, [router]);

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  if (error) return <Screen title="Profile" nav><ErrorText>{error}</ErrorText></Screen>;
  if (!me) return <Screen title="Profile" nav><div className="pt-20 text-center text-stone-400"><Spinner /></div></Screen>;

  const initials = name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <Screen title="Profile" nav>
      <Card className="flex items-center gap-4">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-green-700 text-lg font-semibold text-white">
          {initials}
        </div>
        <div>
          <p className="font-semibold">{name}</p>
          <p className="text-sm text-stone-500">{me.email}</p>
        </div>
      </Card>

      <Card className="p-0 divide-y divide-stone-100 text-sm">
        <div className="flex justify-between px-5 py-4">
          <span className="text-stone-500">Points ($YON)</span>
          <span>{me.points}</span>
        </div>
        <div className="flex justify-between px-5 py-4">
          <span className="text-stone-500">Worth</span>
          <span>{formatMoney(me.points_value_cents, "USD")}</span>
        </div>
        <div className="flex justify-between px-5 py-4">
          <span className="text-stone-500">Minimum to spend</span>
          <span>{me.min_points_to_spend} points</span>
        </div>
      </Card>

      <Button variant="secondary" onClick={handleLogout} className="flex items-center justify-center gap-2">
        <LogOut size={18} /> Log out
      </Button>
    </Screen>
  );
}
