"use client";

import { useEffect, useState } from "react";
import { getPayouts, errorMessage, type Payout } from "@/lib/api";
import { formatMoney, formatDate } from "@/lib/format";
import { storeName, storeLocation } from "@/lib/stores";
import { Screen, Card, Spinner, ErrorText } from "@/components/ui";

export default function PayoutsPage() {
  const [payouts, setPayouts] = useState<Payout[] | null>(null);
  const [error, setError] = useState("");

  // Refresh every 3 seconds so new payouts appear during the demo.
  useEffect(() => {
    const load = () =>
      getPayouts()
        .then(setPayouts)
        .catch((err) => setError(errorMessage(err)));
    load();
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, []);

  return (
    <Screen title="Brand payouts" back="/">
      <p className="-mt-4 text-sm text-stone-500">
        When points are spent, the network settles in USDC and pays the brand in its own currency. Payouts here are
        simulated.
      </p>

      <ErrorText>{error}</ErrorText>

      {!payouts ? (
        <div className="pt-10 text-center text-stone-400"><Spinner /></div>
      ) : payouts.length === 0 ? (
        <p className="text-sm text-stone-400">No payouts yet. They appear here when someone pays with points.</p>
      ) : (
        <Card className="p-0 divide-y divide-stone-100">
          {payouts.map((p) => (
            <div key={p.order_code} className="px-5 py-4 space-y-1">
              <div className="flex items-center justify-between">
                <p className="font-medium">
                  {storeName(p.brand)} <span className="text-stone-400 font-normal">· {storeLocation(p.branch)}</span>
                </p>
                <span className="rounded-full bg-green-50 px-2 py-0.5 text-xs text-green-700">Paid (mock)</span>
              </div>
              <p className="text-sm">
                {formatMoney(p.usdc_cents, "USD")} USDC → <span className="font-medium">{formatMoney(p.local_minor, p.currency)}</span>
              </p>
              <p className="text-xs text-stone-400">
                Order {p.order_code} · {formatDate(p.at)}
              </p>
            </div>
          ))}
        </Card>
      )}
    </Screen>
  );
}
