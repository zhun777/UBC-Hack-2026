"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { MapPin } from "lucide-react";
import { purchase, getUserId, errorMessage, type PurchaseResponse } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { storeName, storeLocation } from "@/lib/stores";
import { Screen, Card, Button, ErrorText, VerifyLink } from "@/components/ui";

const BRAND = "brand-a-us";
const PRODUCT = { name: "Everyday Jacket", amount_minor: 5000, currency: "USD" };

export default function BrandAStorePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<PurchaseResponse | null>(null);

  useEffect(() => {
    if (!getUserId()) router.replace("/login");
  }, [router]);

  async function handleBuy() {
    setLoading(true);
    setError("");
    try {
      setResult(await purchase({ brand: BRAND, ...PRODUCT }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  const price = formatMoney(PRODUCT.amount_minor, PRODUCT.currency);
  const pointsToEarn = Math.floor(PRODUCT.amount_minor / 100);

  return (
    <Screen title={storeName(BRAND)} back="/stores" nav>
      <p className="-mt-4 flex items-center gap-1 text-sm text-stone-500">
        <MapPin size={14} /> {storeLocation(BRAND)}
      </p>

      {result ? (
        <Card className="text-center py-10 space-y-3">
          <p className="text-4xl">✓</p>
          <p className="text-lg font-semibold">Thanks for your order</p>
          <p className="text-green-700 font-medium">+{result.points_earned} points earned</p>
          <VerifyLink url={result.explorer_url} />
          <div className="space-y-2 pt-4">
            <Button onClick={() => setResult(null)}>Buy another</Button>
            <Link href="/" className="block">
              <Button variant="secondary">Back to my points</Button>
            </Link>
          </div>
        </Card>
      ) : (
        <Card className="space-y-5">
          <div className="aspect-square rounded-xl bg-stone-100 flex items-center justify-center text-7xl">🧥</div>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-lg font-semibold">{PRODUCT.name}</p>
              <p className="text-sm text-green-700">Earn {pointsToEarn} points</p>
            </div>
            <p className="text-lg font-semibold">{price}</p>
          </div>
          <Button onClick={handleBuy} loading={loading}>
            Pay {price} by card
          </Button>
          <p className="text-xs text-stone-400 text-center">Card payment is simulated for the demo.</p>
          <ErrorText>{error}</ErrorText>
        </Card>
      )}
    </Screen>
  );
}
