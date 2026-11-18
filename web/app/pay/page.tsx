"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getUserId } from "@/lib/api";
import { Screen, Card, Button } from "@/components/ui";

export default function EnterCodePage() {
  const router = useRouter();
  const [code, setCode] = useState("");

  useEffect(() => {
    if (!getUserId()) router.replace("/login");
  }, [router]);

  function handleSubmit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    router.push(`/pay/${code}`);
  }

  return (
    <Screen title="Pay in store" nav>
      <Card>
        <form onSubmit={handleSubmit} className="space-y-4 text-center">
          <p className="text-sm text-stone-500">Enter the 6-character code on the cashier&apos;s screen</p>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6))}
            placeholder="7K2M9Q"
            autoFocus
            className="w-full rounded-xl border border-stone-300 py-4 text-center font-mono text-3xl tracking-[0.3em] placeholder:text-stone-200 focus:outline-none focus:border-green-700"
          />
          <Button type="submit" disabled={code.length !== 6}>
            Continue
          </Button>
        </form>
      </Card>
    </Screen>
  );
}
