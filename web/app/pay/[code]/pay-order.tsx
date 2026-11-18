"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { getOrder, getMe, payOrder, getUserId, errorMessage, type Order, type Me, type PayResponse } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { storeName, storeLocation } from "@/lib/stores";
import { Screen, Card, Button, Spinner, ErrorText, VerifyLink } from "@/components/ui";

export function PayOrder() {
  const router = useRouter();
  const { code } = useParams<{ code: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [loadError, setLoadError] = useState("");
  const [paying, setPaying] = useState(false);
  const [payError, setPayError] = useState("");
  const [result, setResult] = useState<PayResponse | null>(null);

  useEffect(() => {
    if (!getUserId()) {
      router.replace("/login");
      return;
    }
    Promise.all([getOrder(code), getMe()])
      .then(([o, m]) => {
        setOrder(o);
        setMe(m);
      })
      .catch((err) => setLoadError(errorMessage(err)));
  }, [code, router]);

  async function handlePay() {
    setPaying(true);
    setPayError("");
    try {
      setResult(await payOrder(code));
    } catch (err) {
      setPayError(errorMessage(err));
    } finally {
      setPaying(false);
    }
  }

  if (loadError) {
    return (
      <Screen title="Pay in store" back="/pay" nav>
        <Card className="text-center space-y-4">
          <ErrorText>{loadError}</ErrorText>
          <Link href="/pay" className="block">
            <Button variant="secondary">Try another code</Button>
          </Link>
        </Card>
      </Screen>
    );
  }

  if (!order || !me) {
    return <Screen nav><div className="pt-20 text-center text-stone-400"><Spinner /></div></Screen>;
  }

  const merchant = (
    <div className="text-center">
      <p className="font-medium">{storeName(order.brand)}</p>
      <p className="text-sm text-stone-500">{storeLocation(order.branch)}</p>
    </div>
  );

  if (result) {
    return (
      <Screen nav>
        <Card className="text-center py-10 space-y-3">
          <p className="text-5xl text-green-700">✓</p>
          <p className="text-2xl font-semibold">Paid {formatMoney(order.amount_minor, order.currency)}</p>
          {merchant}
          <p className="text-sm text-stone-500">
            {result.points_applied} points applied
            {result.card_remainder_minor > 0 &&
              ` · ${formatMoney(result.card_remainder_minor, order.currency)} by card (mock)`}
          </p>
          <VerifyLink url={result.explorer_url} />
          <Link href="/" className="block pt-4">
            <Button variant="secondary">Done</Button>
          </Link>
        </Card>
      </Screen>
    );
  }

  const alreadyPaid = order.status === "paid";
  const enoughPoints = me.points >= me.min_points_to_spend;
  const pointsApplied = Math.min(me.points, order.amount_usd_cents);
  const remainderCents = order.amount_usd_cents - pointsApplied;
  // Rough preview in local currency; the backend's answer replaces it after paying.
  const remainderLocal =
    order.amount_usd_cents > 0 ? Math.ceil((remainderCents * order.amount_minor) / order.amount_usd_cents) : 0;

  return (
    <Screen title="Pay in store" back="/pay" nav>
      <Card className="space-y-6">
        {merchant}
        <div className="text-center">
          <p className="text-4xl font-semibold">{formatMoney(order.amount_minor, order.currency)}</p>
          {order.currency !== "USD" && (
            <p className="text-sm text-stone-400">≈ {formatMoney(order.amount_usd_cents, "USD")}</p>
          )}
        </div>

        {alreadyPaid ? (
          <p className="text-center text-stone-500">This order has already been paid.</p>
        ) : !enoughPoints ? (
          <p className="text-center text-sm text-stone-500">
            You need at least {me.min_points_to_spend} points to pay with points. You have {me.points}.
          </p>
        ) : (
          <div className="rounded-xl bg-stone-50 p-4 text-sm space-y-2">
            <div className="flex justify-between">
              <span className="text-stone-500">Points applied</span>
              <span>
                {pointsApplied} ({formatMoney(pointsApplied, "USD")})
              </span>
            </div>
            {remainderCents > 0 && (
              <div className="flex justify-between">
                <span className="text-stone-500">Rest by card (mock)</span>
                <span>{formatMoney(remainderLocal, order.currency)}</span>
              </div>
            )}
            <div className="flex justify-between text-stone-400">
              <span>Points left after</span>
              <span>{me.points - pointsApplied}</span>
            </div>
          </div>
        )}

        <Button onClick={handlePay} loading={paying} disabled={alreadyPaid || !enoughPoints}>
          Pay with points
        </Button>
        <ErrorText>{payError}</ErrorText>
      </Card>
    </Screen>
  );
}
