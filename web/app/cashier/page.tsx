"use client";

import { useEffect, useState } from "react";
import { createPaymentRequest, getOrder, errorMessage, type Order } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { storeName, storeLocation } from "@/lib/stores";
import { Screen, Card, Button, ErrorText } from "@/components/ui";

const MENU = [
  { name: "Kopi", amount_minor: 135 },
  { name: "Teh tarik", amount_minor: 160 },
  { name: "Kaya toast", amount_minor: 270 },
  { name: "Soft-boiled eggs", amount_minor: 180 },
];

export default function CashierPage() {
  const [cart, setCart] = useState<Record<string, number>>({});
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const total = MENU.reduce((sum, item) => sum + item.amount_minor * (cart[item.name] ?? 0), 0);

  // While the order is unpaid, check it every 1.5 seconds.
  const orderCode = order?.order_code;
  const paid = order?.status === "paid";
  useEffect(() => {
    if (!orderCode || paid) return;
    const timer = setInterval(() => {
      getOrder(orderCode).then(setOrder).catch(() => {});
    }, 1500);
    return () => clearInterval(timer);
  }, [orderCode, paid]);

  function add(name: string) {
    setCart({ ...cart, [name]: (cart[name] ?? 0) + 1 });
  }

  async function handleCharge() {
    setLoading(true);
    setError("");
    try {
      const req = await createPaymentRequest({
        brand: "cafe-sg",
        branch: "cafe-sg-orchard",
        amount_minor: total,
        currency: "SGD",
      });
      setOrder(await getOrder(req.order_code));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  function handleNewOrder() {
    setOrder(null);
    setCart({});
  }

  return (
    <Screen title={storeName("cafe-sg")} back="/">
      <p className="-mt-4 text-sm text-stone-500">Cashier · {storeLocation("cafe-sg-orchard")}</p>

      {order ? (
        <Card
          className={`text-center py-10 space-y-4 transition-colors ${
            paid ? "bg-green-700 border-green-700 text-white" : ""
          }`}
        >
          {paid ? (
            <>
              <p className="text-5xl">✓</p>
              <p className="text-2xl font-semibold">Paid</p>
              <p>
                {order.points_applied} points applied
                {order.card_remainder_minor ? ` · ${formatMoney(order.card_remainder_minor, "SGD")} by card` : ""}
              </p>
              <div className="pt-4">
                <Button variant="secondary" className="bg-white" onClick={handleNewOrder}>
                  New order
                </Button>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm text-stone-500">Amount due</p>
              <p className="text-4xl font-semibold">{formatMoney(order.amount_minor, "SGD")}</p>
              {/* The QR code goes here if the Wednesday checkpoint says yes. */}
              <div className="mx-auto w-fit rounded-xl bg-stone-100 px-6 py-4">
                <p className="text-xs text-stone-500 mb-1">Order code</p>
                <p className="font-mono text-3xl tracking-[0.3em]">{order.order_code}</p>
              </div>
              <p className="flex items-center justify-center gap-2 text-sm text-stone-500">
                <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
                Waiting for payment in the $APP app
              </p>
            </>
          )}
        </Card>
      ) : (
        <>
          <Card className="p-0 divide-y divide-stone-100">
            {MENU.map((item) => (
              <button
                key={item.name}
                onClick={() => add(item.name)}
                className="w-full flex items-center justify-between px-5 py-4 hover:bg-stone-50 text-left"
              >
                <span>
                  {item.name}
                  {cart[item.name] ? <span className="ml-2 text-green-700">×{cart[item.name]}</span> : null}
                </span>
                <span className="text-stone-500">{formatMoney(item.amount_minor, "SGD")}</span>
              </button>
            ))}
          </Card>

          <div className="flex items-center justify-between px-1">
            <span className="text-stone-500">Total</span>
            <span className="text-2xl font-semibold">{formatMoney(total, "SGD")}</span>
          </div>

          <Button onClick={handleCharge} loading={loading} disabled={total === 0}>
            Request payment
          </Button>
          {total > 0 && (
            <button onClick={() => setCart({})} className="w-full text-sm text-stone-400 hover:text-stone-900">
              Clear
            </button>
          )}
          <ErrorText>{error}</ErrorText>
        </>
      )}
    </Screen>
  );
}
